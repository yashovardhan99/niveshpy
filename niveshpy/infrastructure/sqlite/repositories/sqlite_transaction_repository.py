"""Repository module for performing CRUD operations on transactions in a SQLite database."""

import datetime
from collections.abc import Iterable, Sequence
from typing import Literal

from attrs import evolve, frozen

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.core.query.prepare import get_fields_from_filters
from niveshpy.domain.repositories import AccountRepository, SecurityRepository
from niveshpy.domain.repositories.transaction_repository import (
    TransactionFetchProfile,
    TransactionSortOrder,
)
from niveshpy.exceptions import DatabaseError, IntegrityError, ResourceNotFoundError
from niveshpy.infrastructure.sqlite.converters import get_converter
from niveshpy.infrastructure.sqlite.query import (
    PRICE_COLUMNS,
    TRANSACTION_COLUMNS,
    TRANSACTION_CREATE_COLUMNS,
    Col,
    Delete,
    Fn,
    Insert,
    Query,
    in_,
    q,
)
from niveshpy.infrastructure.sqlite.query_filters import generate_query_from_filters
from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase
from niveshpy.models.report import Allocation, HoldingUnitRow
from niveshpy.models.transaction import TransactionCreate, TransactionPublic


@frozen
class SqliteTransactionRepository:
    """Repository for performing CRUD operations on transactions in a SQLite database.

    Attributes:
        database: An instance of SqliteDatabase for executing queries.
        account_repository: An instance of AccountRepository for fetching related account data.
        security_repository: An instance of SecurityRepository for fetching related security data.
        account_table_name: The name of the account table in the database.
        security_table_name: The name of the security table in the database.
        transaction_table_name: The name of the transaction table in the database.
        price_table_name: The name of the price table in the database.
    """

    database: SqliteDatabase
    account_repository: AccountRepository
    security_repository: SecurityRepository
    account_table_name = "account"
    security_table_name = "security"
    transaction_table_name = "transaction"
    price_table_name = "price"

    def get_transaction_by_id(
        self,
        transaction_id: int,
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
    ) -> TransactionPublic | None:
        """Fetch a transaction by its unique ID.

        Args:
            transaction_id: The unique ID of the transaction to fetch.
            fetch_profile: The fetch profile to determine the level of detail to retrieve.

        Returns:
            The TransactionPublic object if found, otherwise None.
        """
        query = (
            Query()
            .select(*TRANSACTION_COLUMNS)
            .from_(self.transaction_table_name)
            .where(Col("id").eq(transaction_id))
        )
        result = self.database.select_one(query, cl=TransactionPublic)

        if result is None:
            logger.debug(f"No transaction found with ID {transaction_id}.")
            return None

        if fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
            # We fetch the related account and security data in a separate query
            account = self.account_repository.get_account_by_id(result.account_id)
            security = self.security_repository.get_security_by_key(result.security_key)
            result = evolve(result, account=account, security=security)

        logger.debug(f"Fetched transaction with ID {transaction_id}: {result}")
        return result

    def _update_transactions_with_relations(
        self, transactions: Sequence[TransactionPublic]
    ) -> Sequence[TransactionPublic]:
        """Helper method to update a list of TransactionPublic objects with their related account and security data.

        This is used to fetch related data when the fetch profile requires it.

        Args:
            transactions: A sequence of TransactionPublic objects that may have missing related data.

        Returns:
            A sequence of TransactionPublic objects with related account and security data populated.
        """
        if not transactions:
            return []

        # Fetch all unique account IDs and security keys from the transactions
        account_ids = {txn.account_id for txn in transactions}
        security_keys = {txn.security_key for txn in transactions}

        # Fetch related accounts and securities in bulk to minimize database queries
        accounts = {
            account.id: account
            for account in self.account_repository.find_accounts_by_ids(
                tuple(account_ids)
            )
        }
        securities = {
            security.key: security
            for security in self.security_repository.find_securities_by_keys(
                tuple(security_keys)
            )
        }

        # Update each transaction with its related account and security
        updated_transactions = []
        for txn in transactions:
            account = accounts.get(txn.account_id)
            security = securities.get(txn.security_key)
            if account is None:
                raise ResourceNotFoundError(
                    "Account",
                    identifier=txn.account_id,
                    message=f"Account with ID {txn.account_id} not found for transaction ID {txn.id}.",
                )

            if security is None:
                raise ResourceNotFoundError(
                    "Security",
                    identifier=txn.security_key,
                    message=f"Security with key '{txn.security_key}' not found for transaction ID {txn.id}.",
                )

            updated_txn = evolve(txn, account=account, security=security)
            updated_transactions.append(updated_txn)

        logger.debug(
            "Updated %d transactions with related data.", len(updated_transactions)
        )
        return updated_transactions

    def _update_query_with_sort_order(
        self, query: Query, sort_order: TransactionSortOrder
    ) -> Query:
        if sort_order == TransactionSortOrder.DATE_DESC_ID_ASC:
            return query.order_by(
                "transaction_date DESC",
                "id ASC",
            )
        elif sort_order == TransactionSortOrder.DATE_ASC_ID_ASC:
            return query.order_by(
                "transaction_date ASC",
                "id ASC",
            )
        elif sort_order == TransactionSortOrder.ID_ASC:
            return query.order_by("id ASC")
        elif sort_order == TransactionSortOrder.ID_DESC:
            return query.order_by("id DESC")

    def find_transactions(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
        sort_order: TransactionSortOrder = TransactionSortOrder.DATE_DESC_ID_ASC,
    ) -> Sequence[TransactionPublic]:
        """Find transactions matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter transactions.
            limit: Optional maximum number of transactions to return.
            offset: Optional number of transactions to skip before returning results.
            fetch_profile: The fetch profile to determine the level of detail to retrieve.
            sort_order: The sort order to determine the order of the returned transactions.

        Returns:
            A sequence of TransactionPublic objects matching the filters and pagination criteria.
        """
        filters = list(filters)  # Ensure we can iterate multiple times
        query = (
            generate_query_from_filters(
                filters,
                {
                    Field.AMOUNT: [f"{q(self.transaction_table_name)}.amount"],
                    Field.DATE: [f"{q(self.transaction_table_name)}.transaction_date"],
                    Field.DESCRIPTION: [
                        f"{q(self.transaction_table_name)}.description"
                    ],
                    Field.TYPE: [f"{q(self.transaction_table_name)}.type"],
                    Field.ACCOUNT: [
                        f"{q(self.account_table_name)}.name",
                        f"{q(self.account_table_name)}.institution",
                    ],
                    Field.SECURITY: [
                        f"{q(self.security_table_name)}.key",
                        f"{q(self.security_table_name)}.name",
                        f"{q(self.security_table_name)}.type",
                        f"{q(self.security_table_name)}.category",
                    ],
                },
            )
            .from_(self.transaction_table_name)
            .select(*TRANSACTION_COLUMNS, prefix_table=self.transaction_table_name)
        )
        fields = get_fields_from_filters(filters)

        if Field.ACCOUNT in fields:
            # Only join the Account table if account-related filters are present
            query = query.join(
                self.account_table_name,
                Col("account_id", self.transaction_table_name).eq(
                    Col("id", self.account_table_name)
                ),
            )

        if Field.SECURITY in fields:
            # Only join the Security table if security-related filters are present
            query = query.join(
                self.security_table_name,
                Col("security_key", self.transaction_table_name).eq(
                    Col("key", self.security_table_name)
                ),
            )

        query = self._update_query_with_sort_order(query, sort_order)

        if limit is not None:
            query = query.limit(limit)

        if offset:
            query = query.offset(offset)

        result: Sequence[TransactionPublic] = self.database.select_many(
            query, cl=TransactionPublic
        )
        if fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
            result = self._update_transactions_with_relations(result)

        logger.debug(
            "Found %d transactions matching filters with pagination.", len(result)
        )

        return result

    def find_transactions_by_ids(
        self,
        ids: Sequence[int],
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
        sort_order: TransactionSortOrder = TransactionSortOrder.DATE_DESC_ID_ASC,
    ) -> Sequence[TransactionPublic]:
        """Find transactions matching the given list of IDs.

        Args:
            ids: A sequence of unique IDs to search for.
            fetch_profile: The fetch profile to determine how much related data to load.
            sort_order: The sort order to determine the order of the returned transactions.

        Returns:
            A sequence of TransactionPublic objects matching the given IDs.
        """
        if not ids:
            return []

        query = (
            Query()
            .select(*TRANSACTION_COLUMNS)
            .from_(self.transaction_table_name)
            .where(in_(q(f"{self.transaction_table_name}.id"), *ids))
        )

        query = self._update_query_with_sort_order(query, sort_order)

        transactions = self.database.select_many(query, cl=TransactionPublic)

        if fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
            transactions = self._update_transactions_with_relations(transactions)

        logger.debug(f"Found {len(transactions)} transactions matching IDs")
        return transactions

    def insert_transaction(self, transaction: TransactionCreate) -> int:
        """Insert a new transaction.

        Args:
            transaction: A TransactionCreate object containing the details of the transaction to insert.

        Returns:
            The unique ID of the newly inserted transaction.
        """
        c = get_converter()
        stmt = (
            Insert()
            .into(self.transaction_table_name)
            .columns_(*TRANSACTION_CREATE_COLUMNS)
            .values_(*c.unstructure_attrs_astuple(transaction))
        )
        try:
            with self.database.cursor() as cursor:
                cursor.execute(str(stmt), stmt.params)
                transaction_id = cursor.lastrowid
                cursor.connection.commit()
                logger.debug(f"Inserted transaction with ID {transaction_id}")
                if transaction_id is None:
                    # This should never happen since the ID is auto-generated by the database, but we check just in case to avoid returning None as an int
                    raise DatabaseError(
                        "Failed to insert transaction and retrieve its ID."
                    )
                return transaction_id
        except IntegrityError as e:
            logger.info(f"Failed to insert transaction due to integrity error: {e}")
            if "FOREIGN KEY constraint failed" in str(e):
                raise DatabaseError(
                    "Failed to insert transaction due to foreign key constraint. "
                    "Please ensure the referenced account_id and security_key exist."
                ) from e
            else:
                raise DatabaseError(
                    "Failed to insert transaction due to database integrity error."
                ) from e
        except DatabaseError as e:
            logger.info("Failed to insert transaction due to database error: %s", e)
            raise DatabaseError("Failed to insert transaction") from e

    def insert_multiple_transactions(
        self, transactions: Sequence[TransactionCreate]
    ) -> int:
        """Insert multiple transactions.

        Args:
            transactions: A sequence of TransactionCreate objects to insert.

        Returns:
            The number of transactions successfully inserted.
        """
        if not transactions:
            logger.debug("No transactions provided for bulk insert.")
            return 0
        stmt = (
            Insert()
            .into(self.transaction_table_name)
            .columns_(*TRANSACTION_CREATE_COLUMNS)
        )
        c = get_converter()
        transaction_tuples = [c.unstructure_attrs_astuple(txn) for txn in transactions]
        try:
            result = self.database.executemany(stmt, transaction_tuples)
        except IntegrityError as e:
            logger.info(f"Failed to insert transactions due to integrity error: {e}")
            if "FOREIGN KEY constraint failed" in str(e):
                raise DatabaseError(
                    "Failed to insert transactions due to foreign key constraint. "
                    "Please ensure the referenced account_id and security_key values exist."
                ) from e
            else:
                raise DatabaseError(
                    "Failed to insert transactions due to database integrity error."
                ) from e

        logger.debug(f"Inserted {result} transactions in bulk.")
        return result

    def delete_transaction_by_id(self, transaction_id: int) -> bool:
        """Delete a transaction by its ID.

        Args:
            transaction_id: The unique ID of the transaction to delete.

        Returns:
            True if the transaction was deleted successfully, False if no transaction with the given ID was found.
        """
        stmt = (
            Delete()
            .from_(self.transaction_table_name)
            .where(Col("id").eq(transaction_id))
        )
        result = self.database.execute(stmt)
        if result == 0:
            logger.debug(f"No transaction found with ID {transaction_id} to delete.")
            return False
        logger.debug(f"Deleted transaction with ID {transaction_id}.")
        return True

    def overwrite_transactions_in_date_range_for_accounts(
        self,
        transactions: Sequence[TransactionCreate],
        date_range: tuple[datetime.date, datetime.date],
        account_ids: Sequence[int],
    ) -> int:
        """Bulk insert transactions into the database.

        Delete existing transactions in the date range for specified accounts before inserting.

        Args:
            transactions: A sequence of TransactionCreate objects to insert.
            date_range: A tuple containing the start and end dates (inclusive) as datetime.date objects.
            account_ids: A sequence of account IDs for which to delete existing transactions in the date range before inserting.

        Returns:
            The number of transactions successfully inserted.
        """
        c = get_converter()
        transaction_tuples = [c.unstructure_attrs_astuple(txn) for txn in transactions]
        delete_stmt = (
            Delete()
            .from_(self.transaction_table_name)
            .where(
                Col("transaction_date").between(*date_range),
                Col("account_id").in_(account_ids),
            )
        )
        insert_stmt = (
            Insert()
            .into(self.transaction_table_name)
            .columns_(*TRANSACTION_CREATE_COLUMNS)
        )
        with self.database.cursor() as cursor:
            cursor.execute(str(delete_stmt), delete_stmt.params)
            deleted_count = cursor.rowcount
            logger.debug(
                f"Deleted {deleted_count} existing transactions in date range {date_range} for accounts {account_ids}."
            )
            result = cursor.executemany(str(insert_stmt), transaction_tuples).rowcount
            cursor.connection.commit()
            logger.debug(
                f"Inserted {result} transactions after overwriting in date range {date_range} for accounts {account_ids}."
            )
            return result

    def find_holding_units(
        self, filters: Iterable[FilterNode]
    ) -> Sequence[HoldingUnitRow]:
        """Find holding units matching the given filters.

        Args:
            filters: An iterable of FilterNode objects to filter holding units.

        Returns:
            A sequence of HoldingUnitRow objects matching the given filters.
        """
        filters = list(filters)
        query = generate_query_from_filters(
            filters,
            {
                Field.ACCOUNT: [
                    q(f"{self.account_table_name}.name"),
                    q(f"{self.account_table_name}.institution"),
                ],
                Field.SECURITY: [
                    q(f"{self.security_table_name}.key"),
                    q(f"{self.security_table_name}.name"),
                    q(f"{self.security_table_name}.type"),
                    q(f"{self.security_table_name}.category"),
                ],
            },
        )
        filter_fields = get_fields_from_filters(filters)

        query = (
            query.from_(self.transaction_table_name)
            .select(
                q(f"{self.transaction_table_name}.security_key"),
                q(f"{self.transaction_table_name}.account_id"),
                f"SUM({q(self.transaction_table_name) + '.units'}) AS total_units",
                f"MAX({q(self.transaction_table_name) + '.transaction_date'}) AS last_transaction_date",
            )
            .group_by(
                q(f"{self.transaction_table_name}.account_id"),
                q(f"{self.transaction_table_name}.security_key"),
            )
            .having(Fn("SUM", Col("units", self.transaction_table_name)).ge(0.001))
        )

        if Field.SECURITY in filter_fields:
            query = query.join(
                q(self.security_table_name),
                Col("key", self.security_table_name).eq(
                    Col("security_key", self.transaction_table_name)
                ),
            )
        if Field.ACCOUNT in filter_fields:
            query = query.join(
                q(self.account_table_name),
                Col("id", self.account_table_name).eq(
                    Col("account_id", self.transaction_table_name)
                ),
            )

        results = self.database.select_many(query, cl=HoldingUnitRow)
        logger.debug("Found %d holding unit rows matching filters.", len(results))
        return results

    def find_allocation(
        self,
        filters: Iterable[FilterNode],
        group_by: Literal["category", "type", "both"],
    ) -> Sequence[Allocation]:
        """Find allocations matching the given filters.

        Args:
            filters: An iterable of FilterNode objects to filter allocations.
            group_by: A string indicating how to group the allocations ("category", "type", or "both").

        Returns:
            A sequence of Allocation objects matching the filters and grouped according to the specified criteria.
        """
        filters = list(filters)

        # CTE 1: total units held per security (grouped by security only, not account)
        holding_units_cte = (
            # Transaction filters: security + account only (no date — FIFO needs full history)
            generate_query_from_filters(
                filters,
                {
                    Field.SECURITY: [
                        q(f"{self.security_table_name}.key"),
                        q(f"{self.security_table_name}.name"),
                        q(f"{self.security_table_name}.type"),
                        q(f"{self.security_table_name}.category"),
                    ],
                    Field.ACCOUNT: [
                        q(f"{self.account_table_name}.name"),
                        q(f"{self.account_table_name}.institution"),
                    ],
                },
                include_fields={Field.SECURITY, Field.ACCOUNT},
            )
            .from_(self.transaction_table_name)
            .select(
                q(f"{self.transaction_table_name}.security_key"),
                (f"SUM({q(self.transaction_table_name)}.units)", "total_units"),
                (
                    f"MAX({q(self.transaction_table_name)}.transaction_date)",
                    "last_transaction_date",
                ),
            )
            .group_by(q(f"{self.transaction_table_name}.security_key"))
            .having(Fn("SUM", Col("units", self.transaction_table_name)).ge(0.001))
        )

        # CTE 2: latest price per security (with optional date filter)
        price_cte = (
            generate_query_from_filters(
                # Price filters: security + date (supports "as of date" price lookups)
                filters,
                {
                    Field.SECURITY: [
                        q(f"{self.security_table_name}.key"),
                        q(f"{self.security_table_name}.name"),
                        q(f"{self.security_table_name}.type"),
                        q(f"{self.security_table_name}.category"),
                    ],
                    Field.DATE: [q(f"{self.price_table_name}.date")],
                },
                include_fields={Field.SECURITY, Field.DATE},
            )
            .select(*PRICE_COLUMNS, prefix_table=self.price_table_name)
            .select(
                (
                    f"ROW_NUMBER() OVER (PARTITION BY {q(self.price_table_name)}.security_key ORDER BY {q(self.price_table_name)}.date DESC)",
                    "row_num",
                )
            )
            .from_(self.price_table_name)
        )

        filter_fields = get_fields_from_filters(filters)
        if Field.SECURITY in filter_fields:
            holding_units_cte = holding_units_cte.join(
                q(self.security_table_name),
                Col("key", self.security_table_name).eq(
                    Col("security_key", self.transaction_table_name)
                ),
            )
            price_cte = price_cte.join(
                q(self.security_table_name),
                Col("key", self.security_table_name).eq(
                    Col("security_key", self.price_table_name)
                ),
            )

        if Field.ACCOUNT in filter_fields:
            holding_units_cte = holding_units_cte.join(
                q(self.account_table_name),
                Col("id", self.account_table_name).eq(
                    Col("account_id", self.transaction_table_name)
                ),
            )

        latest_prices_cte = (
            Query()
            .select(*PRICE_COLUMNS, prefix_table="cte_prices")
            .from_("cte_prices")
            .where(Col("row_num").eq(1))
        )

        # CTE 3: holding values joined with security metadata for grouping
        holdings_cte = (
            Query()
            .from_(q(self.security_table_name))
            .join(
                q("holding_units"),
                Col("key", self.security_table_name).eq(
                    Col("security_key", "holding_units")
                ),
            )
            .join(
                q("latest_prices"),
                Col("key", self.security_table_name).eq(
                    Col("security_key", "latest_prices")
                ),
            )
            .select(
                (
                    q(f"{self.security_table_name}.category")
                    if group_by in ("both", "category")
                    else "null",
                    "category",
                ),
                (
                    q(f"{self.security_table_name}.type")
                    if group_by in ("both", "type")
                    else "null",
                    "type",
                ),
                (
                    "holding_units.total_units * latest_prices.close",
                    "holding_value",
                ),
                (
                    "MAX(holding_units.last_transaction_date, latest_prices.date)",
                    "date",
                ),
            )
        )

        # CTE 4: total portfolio value for proportion calculation
        totals_cte = (
            Query()
            .select(
                ("SUM(holding_units.total_units * latest_prices.close)", "total_value")
            )
            .from_(q("holding_units"))
            .join(
                q("latest_prices"),
                Col("security_key", "holding_units").eq(
                    Col("security_key", "latest_prices")
                ),
            )
        )

        # Final: group by category/type and compute proportions
        query = (
            Query()
            .with_cte("holding_units", holding_units_cte)
            .with_cte("cte_prices", price_cte)
            .with_cte("latest_prices", latest_prices_cte)
            .with_cte("holdings", holdings_cte)
            .with_cte("totals", totals_cte)
            .from_("holdings")
            .group_by("holdings.category", "holdings.type")
            .join(q("totals"))
            .select(
                ("MIN(holdings.date)", "date"),
                ("SUM(holdings.holding_value)", "amount"),
                ("(SUM(holdings.holding_value) / totals.total_value)", "allocation"),
                ("holdings.type", "security_type"),
                ("holdings.category", "security_category"),
            )
            .order_by("amount DESC")
        )

        results = self.database.select_many(query, cl=Allocation)
        logger.debug("Found %d allocations matching filters.", len(results))
        return results

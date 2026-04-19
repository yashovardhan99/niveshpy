"""Repository module for performing CRUD operations on transactions in a SQLite database."""

import datetime
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar, Literal

from sqlalchemy.orm import aliased, contains_eager, joinedload, raiseload, selectinload
from sqlalchemy.sql.dml import ReturningInsert
from sqlmodel import col, delete, func, insert, literal, select
from sqlmodel.sql._expression_select_cls import SelectOfScalar

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.core.query.prepare import get_fields_from_filters, get_sqlalchemy_filters
from niveshpy.database import get_session
from niveshpy.domain.repositories.transaction_repository import (
    TransactionFetchProfile,
    TransactionSortOrder,
)
from niveshpy.exceptions import DatabaseError, OperationError
from niveshpy.models.account import Account
from niveshpy.models.price import Price
from niveshpy.models.report import Allocation, HoldingUnitRow
from niveshpy.models.security import Security
from niveshpy.models.transaction import Transaction, TransactionCreate


@dataclass(slots=True, frozen=True)
class SqliteTransactionRepository:
    """Repository for performing CRUD operations on transactions in a SQLite database."""

    _column_mapping: ClassVar[dict[Field, list]] = {
        Field.ACCOUNT: [Account.name, Account.institution],
        Field.AMOUNT: ["amount"],
        Field.DATE: ["transaction_date"],
        Field.DESCRIPTION: ["description"],
        Field.SECURITY: [
            Security.key,
            Security.name,
            Security.type,
            Security.category,
        ],
        Field.TYPE: [Transaction.type],
    }

    def _get_ordered_stmt(
        self, stmt: SelectOfScalar[Transaction], sort_order: TransactionSortOrder
    ) -> SelectOfScalar[Transaction]:
        if sort_order == TransactionSortOrder.DATE_DESC_ID_ASC:
            return stmt.order_by(
                col(Transaction.transaction_date).desc(), col(Transaction.id).asc()
            )
        elif sort_order == TransactionSortOrder.DATE_ASC_ID_ASC:
            return stmt.order_by(
                col(Transaction.transaction_date).asc(), col(Transaction.id).asc()
            )
        elif sort_order == TransactionSortOrder.ID_ASC:
            return stmt.order_by(col(Transaction.id).asc())
        elif sort_order == TransactionSortOrder.ID_DESC:
            return stmt.order_by(col(Transaction.id).desc())
        else:
            # This should never happen since TransactionSortOrder is an enum,
            # but we check just in case to avoid returning an unordered statement
            # if an invalid sort order is somehow passed in
            raise OperationError(f"Unexpected sort order value: {sort_order}")

    def get_transaction_by_id(
        self,
        transaction_id: int,
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
    ) -> Transaction | None:
        """Fetch a transaction by its unique ID.

        Args:
            transaction_id: The unique ID of the transaction to fetch.
            fetch_profile: The fetch profile to determine the level of detail to retrieve.

        Returns:
            The Transaction object if found, otherwise None.
        """
        with get_session() as session:
            stmt: SelectOfScalar[Transaction] = select(Transaction).where(
                Transaction.id == transaction_id
            )
            if fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
                stmt = stmt.options(
                    joinedload(Transaction.account),  # ty:ignore[invalid-argument-type]
                    joinedload(Transaction.security),  # ty:ignore[invalid-argument-type]
                )
            else:
                stmt = stmt.options(
                    raiseload("*")
                )  # Prevent loading any relationships for a more lightweight query

            transaction = session.exec(stmt).first()
            logger.debug(f"Fetched transaction with ID {transaction_id}: {transaction}")
            return transaction

    def find_transactions(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
        sort_order: TransactionSortOrder = TransactionSortOrder.DATE_DESC_ID_ASC,
    ) -> Sequence[Transaction]:
        """Find transactions matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter transactions.
            limit: Optional maximum number of transactions to return.
            offset: Optional number of transactions to skip before returning results.
            fetch_profile: The fetch profile to determine the level of detail to retrieve.
            sort_order: The sort order to determine the order of the returned transactions.

        Returns:
            A sequence of Transaction objects matching the filters and pagination criteria.
        """
        filters = list(filters)
        where_clauses = get_sqlalchemy_filters(
            filters, SqliteTransactionRepository._column_mapping
        )
        fields = get_fields_from_filters(filters)
        stmt = select(Transaction)

        if Field.ACCOUNT in fields:
            # Only join the Account table if account-related filters are present to avoid unnecessary joins for better performance
            stmt = stmt.join(Account)

            if fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
                # Use contains_eager to load the account relationship in the same query
                stmt = stmt.options(contains_eager(Transaction.account))  # ty:ignore[invalid-argument-type]

        elif fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
            # If account is not part of the filters but we want relations, we can still load it with a separate query
            stmt = stmt.options(selectinload(Transaction.account))  # ty:ignore[invalid-argument-type]

        if Field.SECURITY in fields:
            # Only join the Security table if security-related filters are present to avoid unnecessary joins for better performance
            stmt = stmt.join(Security)

            if fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
                # Use contains_eager to load the security relationship in the same query
                stmt = stmt.options(contains_eager(Transaction.security))  # ty:ignore[invalid-argument-type]

        elif fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
            # If security is not part of the filters but we want relations, we can still load it with a separate query
            stmt = stmt.options(selectinload(Transaction.security))  # ty:ignore[invalid-argument-type]

        if fetch_profile == TransactionFetchProfile.MINIMAL:
            stmt = stmt.options(
                raiseload("*")
            )  # Prevent loading any relationships for a more lightweight query

        stmt = stmt.where(*where_clauses)
        stmt = self._get_ordered_stmt(stmt, sort_order)
        stmt = stmt.offset(offset).limit(limit)

        with get_session() as session:
            transactions = session.exec(stmt).all()
            logger.debug(f"Found {len(transactions)} transactions matching filters")
            return transactions

    def find_transactions_by_ids(
        self,
        ids: Sequence[int],
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
        sort_order: TransactionSortOrder = TransactionSortOrder.DATE_DESC_ID_ASC,
    ) -> Sequence[Transaction]:
        """Find transactions matching the given list of IDs.

        Args:
            ids: A sequence of unique IDs to search for.
            fetch_profile: The fetch profile to determine how much related data to load.
            sort_order: The sort order to determine the order of the returned transactions.

        Returns:
            A sequence of Transaction objects matching the given IDs.
        """
        if not ids:
            return []

        stmt: SelectOfScalar[Transaction] = select(Transaction).where(
            col(Transaction.id).in_(ids)
        )

        if fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
            stmt = stmt.options(
                selectinload(Transaction.account),  # ty:ignore[invalid-argument-type]
                selectinload(Transaction.security),  # ty:ignore[invalid-argument-type]
            )
        else:
            stmt = stmt.options(
                raiseload("*")
            )  # Prevent loading any relationships for a more lightweight query

        stmt = self._get_ordered_stmt(stmt, sort_order)

        with get_session() as session:
            transactions = session.exec(stmt).all()
            logger.debug(f"Found {len(transactions)} transactions matching IDs")
            return transactions

    def insert_transaction(self, transaction: TransactionCreate) -> int:
        """Insert a new transaction.

        Args:
            transaction: A TransactionCreate object containing the details of the transaction to insert.

        Returns:
            The unique ID of the newly inserted transaction.
        """
        stmt: ReturningInsert[tuple[int | None]] = (
            insert(Transaction)
            .values(
                transaction_date=transaction.transaction_date,
                type=transaction.type,
                description=transaction.description,
                amount=transaction.amount,
                units=transaction.units,
                security_key=transaction.security_key,
                account_id=transaction.account_id,
                properties=transaction.properties,
            )
            .returning(col(Transaction.id))
        )

        with get_session() as session:
            transaction_id = session.scalar(stmt)
            session.commit()
            logger.debug(f"Inserted transaction with ID {transaction_id}")
            if transaction_id is None:
                # This should never happen since the ID is auto-generated by the database, but we check just in case to avoid returning None as an int
                raise DatabaseError("Failed to insert transaction and retrieve its ID.")
            return transaction_id

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
        transaction_dicts = [
            {
                "transaction_date": transaction.transaction_date,
                "type": transaction.type,
                "description": transaction.description,
                "amount": transaction.amount,
                "units": transaction.units,
                "security_key": transaction.security_key,
                "account_id": transaction.account_id,
                "properties": transaction.properties,
            }
            for transaction in transactions
        ]
        stmt = insert(Transaction).values(transaction_dicts)
        with get_session() as session:
            result = session.exec(stmt).rowcount
            session.commit()
            logger.debug(f"Inserted {result} transactions.")
            return result

    def delete_transaction_by_id(self, transaction_id: int) -> bool:
        """Delete a transaction by its ID.

        Args:
            transaction_id: The unique ID of the transaction to delete.

        Returns:
            True if the transaction was deleted successfully, False if no transaction with the given ID was found.
        """
        stmt = delete(Transaction).where(col(Transaction.id) == transaction_id)
        with get_session() as session:
            result = session.exec(stmt)
            if result.rowcount == 0:
                logger.debug(
                    f"No transaction found with ID {transaction_id} to delete."
                )
                return False
            session.commit()
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
        transaction_dicts = [
            {
                "transaction_date": transaction.transaction_date,
                "type": transaction.type,
                "description": transaction.description,
                "amount": transaction.amount,
                "units": transaction.units,
                "security_key": transaction.security_key,
                "account_id": transaction.account_id,
                "properties": transaction.properties,
            }
            for transaction in transactions
        ]
        with get_session() as session:
            session.exec(
                delete(Transaction).where(
                    col(Transaction.transaction_date) >= date_range[0],
                    col(Transaction.transaction_date) <= date_range[1],
                    col(Transaction.account_id).in_(account_ids),
                )
            )
            result = (
                session.exec(insert(Transaction).values(transaction_dicts)).rowcount
                if transaction_dicts
                else 0
            )
            session.commit()
            logger.debug(
                f"Overwrote transactions in date range {date_range} for accounts {account_ids}. Inserted {result} transactions."
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
        where_clauses = get_sqlalchemy_filters(
            filters,
            {
                Field.ACCOUNT: [Account.name, Account.institution],
                Field.SECURITY: [
                    Security.key,
                    Security.name,
                    Security.type,
                    Security.category,
                ],
            },
        )
        filter_fields = get_fields_from_filters(filters)

        holding_units_stmt = select(
            col(Transaction.security_key),
            col(Transaction.account_id),
            func.sum(Transaction.units).label("total_units"),
            func.max(Transaction.transaction_date).label("last_transaction_date"),
        )
        if Field.SECURITY in filter_fields:
            holding_units_stmt = holding_units_stmt.join(
                Security, col(Security.key) == col(Transaction.security_key)
            )
        if Field.ACCOUNT in filter_fields:
            holding_units_stmt = holding_units_stmt.join(
                Account, col(Account.id) == col(Transaction.account_id)
            )
        holding_units_stmt = (
            holding_units_stmt.where(*where_clauses)
            .group_by(col(Transaction.account_id), col(Transaction.security_key))
            .having(func.sum(Transaction.units) >= Decimal("0.001"))
        )
        with get_session() as session:
            results = session.exec(holding_units_stmt).all()
            holding_unit_rows = [HoldingUnitRow(*result) for result in results]
            logger.debug(
                f"Found {len(holding_unit_rows)} holding unit rows matching filters."
            )
            return holding_unit_rows

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

        # Transaction filters: security + account only (no date — FIFO needs full history)
        txn_where = get_sqlalchemy_filters(
            filters,
            {
                Field.SECURITY: [
                    Security.key,
                    Security.name,
                    Security.type,
                    Security.category,
                ],
                Field.ACCOUNT: [Account.name, Account.institution],
            },
            include_fields={Field.SECURITY, Field.ACCOUNT},
        )
        # Price filters: security + date (supports "as of date" price lookups)
        price_where = get_sqlalchemy_filters(
            filters,
            {
                Field.SECURITY: [
                    Security.key,
                    Security.name,
                    Security.type,
                    Security.category,
                ],
                Field.DATE: [Price.date],
            },
            include_fields={Field.SECURITY, Field.DATE},
        )

        filter_fields = get_fields_from_filters(filters)

        # CTE 1: total units held per security (grouped by security only, not account)
        holding_units_stmt = select(
            col(Transaction.security_key),
            func.max(Transaction.transaction_date).label("last_transaction_date"),
            func.sum(Transaction.units).label("total_units"),
        )
        if Field.SECURITY in filter_fields:
            holding_units_stmt = holding_units_stmt.join(
                Security, col(Security.key) == col(Transaction.security_key)
            )
        if Field.ACCOUNT in filter_fields:
            holding_units_stmt = holding_units_stmt.join(
                Account, col(Account.id) == col(Transaction.account_id)
            )
        holding_units = (
            holding_units_stmt.where(*txn_where)
            .group_by(col(Transaction.security_key))
            .having(func.sum(Transaction.units) >= Decimal("0.001"))
            .cte("holding_units")
        )

        # CTE 2: latest price per security (with optional date filter)
        prices_stmt = select(
            Price,
            func.row_number()
            .over(partition_by=Price.security_key, order_by=col(Price.date).desc())
            .label("row_num"),
        )
        if Field.SECURITY in filter_fields:
            prices_stmt = prices_stmt.join(
                Security, col(Security.key) == col(Price.security_key)
            )
        prices_stmt = prices_stmt.where(*price_where)
        cte_prices = prices_stmt.cte("cte_prices")
        aliased_price = aliased(Price, cte_prices)
        latest_prices = (
            select(aliased_price).where(cte_prices.c.row_num == 1).cte("latest_prices")
        )

        # CTE 3: holding values joined with security metadata for grouping
        cte_holdings = (
            select(
                col(Security.category) if group_by in ("both", "category") else None,
                col(Security.type) if group_by in ("both", "type") else None,
                (holding_units.c.total_units * latest_prices.c.close).label(
                    "holding_value"
                ),
                func.max(
                    holding_units.c.last_transaction_date, latest_prices.c.date
                ).label("date"),
            )
            .join(holding_units, col(Security.key) == holding_units.c.security_key)
            .join(latest_prices, col(Security.key) == latest_prices.c.security_key)
            .cte("cte_holdings")
        )

        # CTE 4: total portfolio value for proportion calculation
        cte_total = select(
            func.sum(cte_holdings.c.holding_value).label("total_value")
        ).cte("cte_total")

        # Final: group by category/type and compute proportions
        stmt = (
            select(
                col(cte_holdings.c.category)
                if group_by in ("both", "category")
                else None,
                col(cte_holdings.c.type) if group_by in ("both", "type") else None,
                func.min(cte_holdings.c.date).label("date"),
                func.sum(cte_holdings.c.holding_value).label("total_amount"),
                (
                    func.sum(cte_holdings.c.holding_value) / cte_total.c.total_value
                ).label("proportion"),
            )  # ty:ignore[no-matching-overload]
            .join(cte_total, literal(True))
            .group_by(
                col(cte_holdings.c.category)
                if group_by in ("both", "category")
                else None,
                col(cte_holdings.c.type) if group_by in ("both", "type") else None,
            )
            .order_by(func.sum(cte_holdings.c.holding_value).desc())
        )

        with get_session() as session:
            results = session.exec(stmt)
            return [
                Allocation(
                    security_category=row[0],
                    security_type=row[1],
                    date=row[2],
                    amount=Decimal(str(row[3])).quantize(Decimal("0.01")),
                    allocation=Decimal(str(row[4])).quantize(Decimal("0.0001")),
                )
                for row in results
            ]

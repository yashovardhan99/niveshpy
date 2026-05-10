"""Repository module for account-related database operations."""

from collections.abc import Iterable, Sequence

from attrs import frozen

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.exceptions import InvalidInputError
from niveshpy.infrastructure.sqlite.converters import get_converter
from niveshpy.infrastructure.sqlite.query import (
    ACCOUNT_COLUMNS,
    Delete,
    Insert,
    Query,
    in_,
)
from niveshpy.infrastructure.sqlite.query_filters import generate_query_from_filters
from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase
from niveshpy.models.account import AccountCreate, AccountPublic


@frozen
class SqliteAccountRepository:
    """Repository for performing database operations related to accounts.

    Attributes:
        database: The SqliteDatabase instance used for executing queries.
        account_table_name: The name of the accounts table in the database.
    """

    database: SqliteDatabase
    account_table_name: str = "account"

    # SELECT operations for single account

    def get_account_by_id(self, account_id: int) -> AccountPublic | None:
        """Fetch an account by its ID."""
        query = (
            Query()
            .select(*ACCOUNT_COLUMNS)
            .from_(self.account_table_name)
            .where(("id = ?", account_id))
        )
        return self.database.select_one(query, cl=AccountPublic)

    def get_account_by_name_and_institution(
        self, name: str, institution: str
    ) -> AccountPublic | None:
        """Fetch an account by its name and institution."""
        query = (
            Query()
            .select(*ACCOUNT_COLUMNS)
            .from_(self.account_table_name)
            .where(("name = ?", name), ("institution = ?", institution))
        )
        return self.database.select_one(query, cl=AccountPublic)

    # SELECT operations for multiple accounts

    def find_accounts(
        self, filters: Iterable[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[AccountPublic]:
        """Find accounts matching the given filters with optional pagination."""
        query = (
            generate_query_from_filters(
                filters,
                {
                    Field.ACCOUNT: ["name", "institution"],
                },
            )
            .from_(self.account_table_name)
            .select(*ACCOUNT_COLUMNS)
            .order_by("id")
        )
        if limit is not None:
            query = query.limit(limit)
        if offset > 0:
            query = query.offset(offset)
        return self.database.select_many(query, cl=AccountPublic)

    def find_accounts_by_ids(
        self, account_ids: Sequence[int]
    ) -> Sequence[AccountPublic]:
        """Find accounts matching the given sequence of IDs.

        Args:
            account_ids: A sequence of account IDs to search for.

        Returns:
            A sequence of AccountPublic objects matching the given IDs.
        """
        if not account_ids:
            logger.debug("No account IDs provided for search.")
            return []
        query = (
            Query()
            .select(*ACCOUNT_COLUMNS)
            .from_(self.account_table_name)
            .where(in_("id", *account_ids))
        )
        return self.database.select_many(query, cl=AccountPublic)

    def find_accounts_by_name_and_institutions(
        self, names: Sequence[str], institutions: Sequence[str]
    ) -> Sequence[AccountPublic]:
        """Find accounts matching the given name-institution pairs."""
        if not names or not institutions:
            logger.debug("No names or institutions provided for account search.")
            return []
        if len(names) != len(institutions):
            raise InvalidInputError(
                (names, institutions),
                "Names and institutions lists must be of the same length.",
            )
        query = (
            Query()
            .select(*ACCOUNT_COLUMNS)
            .from_(self.account_table_name)
            .where(
                in_(
                    ("name", "institution"),
                    *zip(names, institutions, strict=True),
                )
            )
        )
        return self.database.select_many(query, cl=AccountPublic)

    # # INSERT operations for single account

    def insert_account(self, account: AccountCreate) -> int | None:
        """Insert a new account into the database."""
        c = get_converter()
        stmt = (
            Insert(self.account_table_name)
            .or_ignore()
            .columns_("name", "institution", "properties")
            .values_(*c.unstructure_attrs_astuple(account))
            .returning("id")
        )
        with self.database.cursor() as cursor:
            result = cursor.execute(str(stmt), stmt.params)
            inserted_account_row = result.fetchone()
        if inserted_account_row is not None:
            inserted_account_id = inserted_account_row[0]
            logger.debug("Inserted new account with ID: %d", inserted_account_id)
        else:
            logger.debug("Account already exists, skipping insert: %s", account)
            inserted_account_id = None
        return inserted_account_id

    # # INSERT operations for multiple accounts

    def insert_multiple_accounts(self, accounts: Iterable[AccountCreate]) -> int:
        """Insert multiple accounts into the database."""
        c = get_converter()
        account_tuples = [c.unstructure_attrs_astuple(account) for account in accounts]

        if not account_tuples:
            logger.debug("No accounts to insert.")
            return 0

        stmt = (
            Insert(self.account_table_name)
            .or_ignore()
            .columns_("name", "institution", "properties")
        )
        result = self.database.executemany(stmt, account_tuples)
        logger.debug("Inserted %d new accounts.", result)
        return result

    # # DELETE operations for single account

    def delete_account_by_id(self, account_id: int) -> bool:
        """Delete an account by its ID."""
        stmt = Delete(self.account_table_name).where(("id = ?", account_id))
        result = self.database.execute(stmt)
        if result == 0:
            logger.debug("No account found with ID %d to delete.", account_id)
            return False
        logger.debug("Deleted account with ID %d.", account_id)
        return True

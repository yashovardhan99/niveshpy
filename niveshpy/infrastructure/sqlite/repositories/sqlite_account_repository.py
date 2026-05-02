"""Repository module for account-related database operations."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import cast

from sqlalchemy import CursorResult, delete, select, tuple_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.core.query.prepare import get_sqlalchemy_filters
from niveshpy.exceptions import InvalidInputError
from niveshpy.infrastructure.sqlite.models import Account
from niveshpy.models.account import AccountCreate, AccountPublic


@dataclass(slots=True, frozen=True)
class SqliteAccountRepository:
    """Repository for performing database operations related to accounts.

    Attributes:
        session_factory: The sessionmaker instance used for creating database sessions.
    """

    session_factory: sessionmaker[Session]

    # SELECT operations for single account

    def get_account_by_id(self, account_id: int) -> AccountPublic | None:
        """Fetch an account by its ID."""
        with self.session_factory() as session:
            account = session.get(Account, account_id)
            logger.debug("Fetched account by ID %d: %s", account_id, str(account))
            return account.to_public() if account else None

    def get_account_by_name_and_institution(
        self, name: str, institution: str
    ) -> AccountPublic | None:
        """Fetch an account by its name and institution."""
        query = select(Account).where(
            Account.name == name, Account.institution == institution
        )
        with self.session_factory() as session:
            account = session.scalar(query)
            logger.debug(
                "Fetched account by name '%s' and institution '%s': %s",
                name,
                institution,
                str(account),
            )
            return account.to_public() if account else None

    # SELECT operations for multiple accounts

    def find_accounts(
        self, filters: Iterable[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[AccountPublic]:
        """Find accounts matching the given filters with optional pagination."""
        where_clause = get_sqlalchemy_filters(
            filters,
            {
                Field.ACCOUNT: ["name", "institution"],
            },
        )
        with self.session_factory() as session:
            accounts = session.scalars(
                select(Account)
                .where(*where_clause)
                .offset(offset)
                .limit(limit)
                .order_by(Account.id)
            ).all()
            logger.debug("Fetched %d accounts with filters: %s", len(accounts), filters)
            return [account.to_public() for account in accounts]

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
        query = select(Account).where(Account.id.in_(account_ids))
        with self.session_factory() as session:
            accounts = session.scalars(query).all()
            logger.debug(
                "Fetched %d accounts with IDs in %s", len(accounts), account_ids
            )
            return [account.to_public() for account in accounts]

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
        query = select(Account).where(
            tuple_(Account.name, Account.institution).in_(
                zip(names, institutions, strict=True)
            )
        )
        with self.session_factory() as session:
            accounts = session.scalars(query).all()
            logger.debug(
                "Fetched %d accounts with names in %s and institutions in %s",
                len(accounts),
                names,
                institutions,
            )
            return [account.to_public() for account in accounts]

    # INSERT operations for single account

    def insert_account(self, account: AccountCreate) -> int | None:
        """Insert a new account into the database."""
        with self.session_factory.begin() as session:
            stmt = (
                sqlite_insert(Account)
                .values(
                    name=account.name,
                    institution=account.institution,
                    properties=account.properties,
                )
                .on_conflict_do_nothing()
                .returning(Account.id)
            )
            inserted_account_id = session.scalar(stmt)
        if inserted_account_id is not None:
            logger.debug("Inserted new account with ID: %d", inserted_account_id)
        else:
            logger.debug("Account already exists, skipping insert: %s", account)
        return inserted_account_id

    # INSERT operations for multiple accounts

    def insert_multiple_accounts(self, accounts: Iterable[AccountCreate]) -> int:
        """Insert multiple accounts into the database."""
        account_dicts = [
            {
                "name": account.name,
                "institution": account.institution,
                "properties": account.properties,
            }
            for account in accounts
        ]
        if not account_dicts:
            logger.debug("No accounts to insert.")
            return 0
        with self.session_factory.begin() as session:
            stmt = sqlite_insert(Account).values(account_dicts).on_conflict_do_nothing()
            result = cast(CursorResult, session.execute(stmt))
        logger.debug("Inserted %d new accounts.", result.rowcount)
        return result.rowcount

    # DELETE operations for single account

    def delete_account_by_id(self, account_id: int) -> bool:
        """Delete an account by its ID."""
        with self.session_factory.begin() as session:
            stmt = delete(Account).where(Account.id == account_id)
            result = cast(CursorResult, session.execute(stmt))
            if result.rowcount == 0:
                logger.debug("No account found with ID %d to delete.", account_id)
                return False
        logger.debug("Deleted account with ID %d.", account_id)
        return True

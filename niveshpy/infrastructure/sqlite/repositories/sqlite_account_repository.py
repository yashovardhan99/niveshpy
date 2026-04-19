"""Repository module for account-related database operations."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy import tuple_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import col, delete, select

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.core.query.prepare import get_sqlalchemy_filters
from niveshpy.database import get_session
from niveshpy.exceptions import InvalidInputError
from niveshpy.models.account import Account, AccountCreate


@dataclass(slots=True, frozen=True)
class SqliteAccountRepository:
    """Repository for performing database operations related to accounts."""

    _column_mappings: ClassVar[dict[Field, list[str]]] = {
        Field.ACCOUNT: ["name", "institution"],
    }

    # SELECT operations for single account

    def get_account_by_id(self, account_id: int) -> Account | None:
        """Fetch an account by its ID."""
        with get_session() as session:
            account = session.get(Account, account_id)
            logger.debug("Fetched account by ID %d: %s", account_id, str(account))
            return account

    def get_account_by_name_and_institution(
        self, name: str, institution: str
    ) -> Account | None:
        """Fetch an account by its name and institution."""
        query = select(Account).where(
            col(Account.name) == name, col(Account.institution) == institution
        )
        with get_session() as session:
            account = session.exec(query).one_or_none()
            logger.debug(
                "Fetched account by name '%s' and institution '%s': %s",
                name,
                institution,
                str(account),
            )
            return account

    # SELECT operations for multiple accounts

    def find_accounts(
        self, filters: Iterable[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[Account]:
        """Find accounts matching the given filters with optional pagination."""
        where_clause = get_sqlalchemy_filters(
            filters, SqliteAccountRepository._column_mappings
        )
        with get_session() as session:
            accounts = session.exec(
                select(Account)
                .where(*where_clause)
                .offset(offset)
                .limit(limit)
                .order_by(col(Account.id))
            ).all()
            logger.debug("Fetched %d accounts with filters: %s", len(accounts), filters)
            return accounts

    def find_accounts_by_ids(self, account_ids: Sequence[int]) -> Sequence[Account]:
        """Find accounts matching the given sequence of IDs.

        Args:
            account_ids: A sequence of account IDs to search for.

        Returns:
            A sequence of Account objects matching the given IDs.
        """
        if not account_ids:
            logger.debug("No account IDs provided for search.")
            return []
        query = select(Account).where(col(Account.id).in_(account_ids))
        with get_session() as session:
            accounts = session.exec(query).all()
            logger.debug(
                "Fetched %d accounts with IDs in %s", len(accounts), account_ids
            )
            return accounts

    def find_accounts_by_name_and_institutions(
        self, names: Sequence[str], institutions: Sequence[str]
    ) -> Sequence[Account]:
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
            tuple_(col(Account.name), col(Account.institution)).in_(
                zip(names, institutions, strict=True)
            )
        )
        with get_session() as session:
            accounts = session.exec(query).all()
            logger.debug(
                "Fetched %d accounts with names in %s and institutions in %s",
                len(accounts),
                names,
                institutions,
            )
            return accounts

    # INSERT operations for single account

    def insert_account(self, account: AccountCreate) -> int | None:
        """Insert a new account into the database."""
        with get_session() as session:
            stmt = (
                sqlite_insert(Account)
                .values(
                    name=account.name,
                    institution=account.institution,
                    properties=account.properties,
                )
                .on_conflict_do_nothing()
                .returning(col(Account.id))
            )
            inserted_account_id = session.scalar(stmt)
            session.commit()
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
        with get_session() as session:
            stmt = sqlite_insert(Account).values(account_dicts).on_conflict_do_nothing()
            result = session.exec(stmt).rowcount
            session.commit()
            logger.debug("Inserted %d new accounts.", result)
            return result

    # DELETE operations for single account

    def delete_account_by_id(self, account_id: int) -> bool:
        """Delete an account by its ID."""
        with get_session() as session:
            stmt = delete(Account).where(col(Account.id) == account_id)
            result = session.exec(stmt)
            if result.rowcount == 0:
                logger.debug("No account found with ID %d to delete.", account_id)
                return False
            session.commit()
            logger.debug("Deleted account with ID %d.", account_id)
            return True

"""Repository module for account-related database operations."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import col, delete, select

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.core.query.prepare import get_sqlalchemy_filters
from niveshpy.database import get_session
from niveshpy.models.account import Account


@dataclass(slots=True, frozen=True)
class AccountRepository:
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

    def list_accounts(
        self, filters: Iterable[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[Account]:
        """List accounts with optional filtering, pagination, and sorting."""
        where_clause = get_sqlalchemy_filters(
            filters, AccountRepository._column_mappings
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

    # INSERT operations for single account

    def insert_account(self, account: Account) -> int | None:
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

    def insert_multiple_accounts(self, accounts: Iterable[Account]) -> int:
        """Insert multiple accounts into the database."""
        account_dicts = [
            {
                "name": account.name,
                "institution": account.institution,
                "properties": account.properties,
            }
            for account in accounts
        ]
        if len(account_dicts) == 0:
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

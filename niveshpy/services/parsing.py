"""Service for parsing financial documents."""

from collections.abc import Callable, Sequence
from datetime import date
from typing import TypeVar

from pydantic import RootModel
from sqlalchemy import (
    tuple_,  # TODO: Replace with tuple_ from sqlmodel once https://github.com/fastapi/sqlmodel/pull/1639 is merged
)
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlmodel import col, delete, insert, select

from niveshpy.database import get_session
from niveshpy.models.account import (
    Account,
    AccountCreate,
    AccountPublic,
)
from niveshpy.models.parser import Parser
from niveshpy.models.security import (
    Security,
    SecurityCreate,
)
from niveshpy.models.transaction import (
    Transaction,
    TransactionCreate,
    TransactionPublic,
)


class ParsingService:
    """Service for parsing financial documents."""

    def __init__(
        self,
        parser: Parser,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ):
        """Initialize the ParsingService."""
        self._parser: Parser = parser
        self._progress_callback = progress_callback

    def _report_progress(self, stage: str, current: int, total: int) -> None:
        """Report progress if a callback is provided."""
        if self._progress_callback:
            self._progress_callback(stage, current, total)

    def parse_and_store_all(self) -> None:
        """Parse and store all data using the parser.

        Args:
            progress_callback: Optional callback(stage, current, total) for progress updates
                - stage: "accounts", "securities", "transactions"
                - current: current item count
                - total: total items (or -1 if unknown)
        """
        accounts = self._parse_accounts()
        securities = self._parse_securities()
        self._parse_transactions(accounts, securities)

    _T = TypeVar("_T", SecurityCreate, AccountCreate, TransactionCreate)

    def _add_metadata(self, item: _T) -> _T:
        """Add metadata to a parsed item."""
        if item.properties.get("source") is None:
            item.properties["source"] = "parser"
        return item

    def _bulk_insert_accounts(
        self, accounts: list[AccountCreate]
    ) -> list[AccountPublic]:
        """Bulk insert accounts into the database."""
        if len(accounts) == 0:
            return []
        account_dicts = RootModel[list[Account]].model_validate(accounts).model_dump()
        with get_session() as session:
            session.exec(
                sqlite_upsert(Account).on_conflict_do_nothing(
                    index_elements=["name", "institution"],
                ),
                params=account_dicts,
            )
            session.commit()
            search_keys: list[tuple[str, str]] = [
                (account.name, account.institution) for account in accounts
            ]
            res = session.scalars(
                select(Account).where(
                    tuple_(col(Account.name), col(Account.institution)).in_(search_keys)
                )
            )
            return [AccountPublic.model_validate(acc) for acc in res.all()]

    def _bulk_insert_securities(
        self, securities: list[SecurityCreate]
    ) -> list[Security]:
        """Bulk insert securities into the database."""
        if len(securities) == 0:
            return []
        security_dicts = (
            RootModel[list[Security]].model_validate(securities).model_dump()
        )
        with get_session() as session:
            session.exec(
                sqlite_upsert(Security).on_conflict_do_nothing(index_elements=["key"]),
                params=security_dicts,
            )
            session.commit()
            res = session.scalars(
                select(Security).where(
                    col(Security.key).in_([sec.key for sec in securities])
                )
            )
            return [Security.model_validate(sec) for sec in res.all()]

    def _bulk_insert_transactions(
        self,
        transactions: list[TransactionCreate],
        date_range: tuple[date, date],
        account_ids: list[int],
    ) -> list[TransactionPublic]:
        """Bulk insert transactions into the database.

        Delete existing transactions in the date range for specified accounts before inserting.
        """
        transaction_dicts = (
            RootModel[list[Transaction]].model_validate(transactions).model_dump()
        )
        with get_session() as session:
            session.exec(
                delete(Transaction).where(
                    col(Transaction.transaction_date) >= date_range[0],
                    col(Transaction.transaction_date) <= date_range[1],
                    col(Transaction.account_id).in_(account_ids),
                )
            )
            results: Sequence[Transaction] = (
                session.scalars(
                    insert(Transaction).returning(Transaction),
                    transaction_dicts,
                ).all()
                if len(transaction_dicts) > 0
                else []
            )
            session.commit()
            return RootModel[list[TransactionPublic]].model_validate(results).root

    def _parse_accounts(self) -> list[AccountPublic]:
        """Parse and store accounts using the parser."""
        self._report_progress("accounts", 0, -1)
        accounts = [
            self._add_metadata(account) for account in self._parser.get_accounts()
        ]
        self._report_progress("accounts", 0, len(accounts))
        refreshed_accounts = self._bulk_insert_accounts(accounts)
        self._report_progress("accounts", len(refreshed_accounts), len(accounts))
        return refreshed_accounts

    def _parse_securities(self) -> list[Security]:
        """Parse and store securities using the parser."""
        self._report_progress("securities", 0, -1)
        securities = list(map(self._add_metadata, self._parser.get_securities()))
        self._report_progress("securities", 0, len(securities))
        refreshed_securities = self._bulk_insert_securities(securities)
        self._report_progress("securities", len(refreshed_securities), len(securities))
        return refreshed_securities

    def _parse_transactions(
        self, accounts: list[AccountPublic], securities: list[Security]
    ) -> None:
        """Parse and store transactions using the parser."""
        self._report_progress("transactions", 0, -1)
        transactions = list(
            map(self._add_metadata, self._parser.get_transactions(accounts))
        )
        self._report_progress("transactions", 0, len(transactions))
        account_ids = [account.id for account in accounts]
        inserted = self._bulk_insert_transactions(
            transactions, self._parser.get_date_range(), account_ids
        )
        self._report_progress("transactions", len(inserted), len(transactions))

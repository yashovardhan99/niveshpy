"""Service for parsing financial documents."""

# import polars as pl
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from pydantic import RootModel
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from niveshpy.database import session
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.models.account import (
    Account,
    AccountCreate,
    AccountPublic,
)
from niveshpy.models.parser import Parser
from niveshpy.models.security import SecurityRead, SecurityWrite
from niveshpy.models.transaction import TransactionWrite


class ParsingService:
    """Service for parsing financial documents."""

    def __init__(
        self,
        parser: Parser,
        repos: RepositoryContainer,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ):
        """Initialize the ParsingService."""
        self._parser = parser
        self._repos = repos
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
        with ThreadPoolExecutor() as executor:
            # Parse accounts and securities in parallel
            accounts_future = executor.submit(self._parse_accounts)
            securities_future = executor.submit(self._parse_securities)

            accounts = accounts_future.result()
            securities = securities_future.result()

        # Parse transactions after accounts and securities are done
        self._parse_transactions(accounts, securities)

    _T = TypeVar("_T", SecurityWrite, AccountCreate, TransactionWrite)

    def _add_metadata(self, item: _T) -> _T:
        """Add metadata to a parsed item."""
        if isinstance(item, AccountCreate):
            if item.properties.get("source") is None:
                item.properties["source"] = "parser"
        elif hasattr(item, "metadata"):
            if item.metadata.get("source") is None:
                item.metadata["source"] = "parser"
        return item

    def _bulk_insert_accounts(
        self, accounts: list[AccountCreate]
    ) -> list[AccountPublic]:
        """Bulk insert accounts into the database."""
        # TODO: Implement bulk insert logic
        account_dicts = RootModel[list[Account]].model_validate(accounts).model_dump()
        with session() as sql_session:
            stm = sqlite_upsert(Account)
            res = sql_session.scalars(
                stm.on_conflict_do_update(
                    index_elements=["name", "institution"],
                    set_={"properties": stm.excluded.properties},
                ).returning(Account),
                account_dicts,
            )
            sql_session.commit()
            return RootModel[list[AccountPublic]].model_validate(res.all()).root

    def _parse_accounts(self) -> list[AccountPublic]:
        """Parse and store accounts using the parser."""
        self._report_progress("accounts", 0, -1)
        accounts = list(map(self._add_metadata, self._parser.get_accounts()))
        self._report_progress("accounts", 0, len(accounts))
        inserted_accounts = self._bulk_insert_accounts(accounts)
        self._report_progress("accounts", len(inserted_accounts), len(accounts))
        return inserted_accounts

    def _parse_securities(self) -> list[SecurityRead]:
        """Parse and store securities using the parser."""
        self._report_progress("securities", 0, -1)
        securities = list(map(self._add_metadata, self._parser.get_securities()))
        self._report_progress("securities", 0, len(securities))
        inserted = self._repos.security.insert_multiple_securities(securities)
        self._report_progress("securities", len(inserted), len(securities))
        return inserted

    def _parse_transactions(
        self, accounts: list[AccountPublic], securities: list[SecurityRead]
    ) -> None:
        """Parse and store transactions using the parser."""
        self._report_progress("transactions", 0, -1)
        transactions = list(
            map(self._add_metadata, self._parser.get_transactions(accounts))
        )
        self._report_progress("transactions", 0, len(transactions))
        self._repos.transaction.insert_multiple_transactions(
            transactions, accounts, securities, self._parser.get_date_range()
        )
        self._report_progress("transactions", len(transactions), len(transactions))

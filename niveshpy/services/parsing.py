"""Service for parsing financial documents."""

# import polars as pl
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from niveshpy.db.repositories import RepositoryContainer
from niveshpy.models.account import AccountRead, AccountWrite
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

    _T = TypeVar("_T", SecurityWrite, AccountWrite, TransactionWrite)

    def _add_metadata(self, item: _T) -> _T:
        """Add metadata to a parsed item."""
        if item.metadata.get("source") is None:
            item.metadata["source"] = "parser"
        return item

    def _parse_accounts(self) -> list[AccountRead]:
        """Parse and store accounts using the parser."""
        self._report_progress("accounts", 0, -1)
        accounts = list(map(self._add_metadata, self._parser.get_accounts()))
        self._report_progress("accounts", 0, len(accounts))
        inserted_accounts = self._repos.account.insert_multiple_accounts(accounts)
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
        self, accounts: list[AccountRead], securities: list[SecurityRead]
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

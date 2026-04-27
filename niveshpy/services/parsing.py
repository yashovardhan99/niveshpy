"""Service for parsing financial documents."""

from collections.abc import Callable, Sequence
from typing import TypeVar

from attrs import evolve, field, frozen

from niveshpy.domain.repositories import (
    AccountRepository,
    SecurityRepository,
    TransactionRepository,
)
from niveshpy.models.account import AccountCreate, AccountPublic
from niveshpy.models.parser import Parser
from niveshpy.models.security import SecurityCreate
from niveshpy.models.transaction import TransactionCreate


@frozen
class ParsingService:
    """Service for parsing financial documents."""

    _parser: Parser = field(alias="parser")
    _account_repository: AccountRepository = field(alias="account_repository")
    _security_repository: SecurityRepository = field(alias="security_repository")
    _transaction_repository: TransactionRepository = field(
        alias="transaction_repository"
    )
    _progress_callback: Callable[[str, int, int], None] | None = field(
        default=None, alias="progress_callback"
    )

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
        self._parse_securities()
        self._parse_transactions(accounts)

    _T = TypeVar("_T", SecurityCreate, AccountCreate, TransactionCreate)

    def _add_metadata(self, item: _T) -> _T:
        """Add metadata to a parsed item."""
        if item.properties.get("source") is None:
            if isinstance(item, (AccountCreate, SecurityCreate)):
                item = evolve(item, properties={**item.properties, "source": "parser"})
            else:
                item.properties["source"] = "parser"
        return item

    def _bulk_insert_accounts(
        self, accounts: list[AccountCreate]
    ) -> Sequence[AccountPublic]:
        """Bulk insert accounts into the database."""
        if len(accounts) == 0:
            return []
        self._account_repository.insert_multiple_accounts(accounts)
        included_accounts = (
            self._account_repository.find_accounts_by_name_and_institutions(
                names=[account.name for account in accounts],
                institutions=[account.institution for account in accounts],
            )
        )
        return included_accounts

    def _bulk_insert_securities(self, securities: list[SecurityCreate]) -> None:
        """Bulk insert securities into the database."""
        if len(securities) != 0:
            self._security_repository.insert_multiple_securities(securities)

    def _parse_accounts(self) -> Sequence[AccountPublic]:
        """Parse and store accounts using the parser."""
        self._report_progress("accounts", 0, -1)
        accounts = [
            self._add_metadata(account) for account in self._parser.get_accounts()
        ]
        self._report_progress("accounts", 0, len(accounts))
        refreshed_accounts = self._bulk_insert_accounts(accounts)
        self._report_progress("accounts", len(refreshed_accounts), len(accounts))
        return refreshed_accounts

    def _parse_securities(self) -> None:
        """Parse and store securities using the parser."""
        self._report_progress("securities", 0, -1)
        securities = list(map(self._add_metadata, self._parser.get_securities()))
        self._report_progress("securities", 0, len(securities))
        self._bulk_insert_securities(securities)
        self._report_progress("securities", len(securities), len(securities))

    def _parse_transactions(self, accounts: Sequence[AccountPublic]) -> None:
        """Parse and store transactions using the parser."""
        self._report_progress("transactions", 0, -1)
        transactions = list(
            map(self._add_metadata, self._parser.get_transactions(accounts))
        )
        self._report_progress("transactions", 0, len(transactions))
        account_ids = [account.id for account in accounts]
        inserted_count = self._transaction_repository.overwrite_transactions_in_date_range_for_accounts(
            transactions, self._parser.get_date_range(), account_ids
        )
        self._report_progress("transactions", inserted_count, len(transactions))

"""Service for parsing financial documents."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import TypeVar

from pydantic import RootModel
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlmodel import delete, insert

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
        self._parser = parser
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
        # TODO: Implement bulk insert logic
        account_dicts = RootModel[list[Account]].model_validate(accounts).model_dump()
        with get_session() as session:
            stm = sqlite_upsert(Account)
            res = session.scalars(
                stm.on_conflict_do_update(
                    index_elements=["name", "institution"],
                    set_={"properties": stm.excluded.properties},
                ).returning(Account),
                account_dicts,
            )
            session.commit()
            return RootModel[list[AccountPublic]].model_validate(res.all()).root

    def _bulk_insert_securities(
        self, securities: list[SecurityCreate]
    ) -> list[Security]:
        """Bulk insert securities into the database."""
        # TODO: Implement bulk insert logic
        security_dicts = (
            RootModel[list[Security]].model_validate(securities).model_dump()
        )
        with get_session() as session:
            stm = sqlite_upsert(Security)
            res = session.scalars(
                stm.on_conflict_do_update(
                    index_elements=["key"],
                    set_={
                        "name": stm.excluded.name,
                        "type": stm.excluded.type,
                        "category": stm.excluded.category,
                        "properties": stm.excluded.properties,
                    },
                ).returning(Security),
                security_dicts,
            )
            session.commit()
            return RootModel[list[Security]].model_validate(res.all()).root

    def _bulk_insert_transactions(
        self,
        transactions: list[TransactionCreate],
        date_range: tuple[date, date],
    ) -> list[TransactionPublic]:
        """Bulk insert transactions into the database.

        Delete existing transactions in the date range before inserting.
        """
        transaction_dicts = (
            RootModel[list[Transaction]].model_validate(transactions).model_dump()
        )
        with get_session() as session:
            session.exec(
                delete(Transaction).where(
                    Transaction.transaction_date >= date_range[0],  # type: ignore[arg-type]
                    Transaction.transaction_date <= date_range[1],  # type: ignore[arg-type]
                )
            )
            results = session.scalars(
                insert(Transaction).returning(Transaction),
                transaction_dicts,
            )
            session.commit()
            return RootModel[list[TransactionPublic]].model_validate(results).root

    def _parse_accounts(self) -> list[AccountPublic]:
        """Parse and store accounts using the parser."""
        self._report_progress("accounts", 0, -1)
        accounts = list(map(self._add_metadata, self._parser.get_accounts()))
        self._report_progress("accounts", 0, len(accounts))
        inserted_accounts = self._bulk_insert_accounts(accounts)
        self._report_progress("accounts", len(inserted_accounts), len(accounts))
        return inserted_accounts

    def _parse_securities(self) -> list[Security]:
        """Parse and store securities using the parser."""
        self._report_progress("securities", 0, -1)
        securities = list(map(self._add_metadata, self._parser.get_securities()))
        self._report_progress("securities", 0, len(securities))
        inserted = self._bulk_insert_securities(securities)
        self._report_progress("securities", len(inserted), len(securities))
        return inserted

    def _parse_transactions(
        self, accounts: list[AccountPublic], securities: list[Security]
    ) -> None:
        """Parse and store transactions using the parser."""
        self._report_progress("transactions", 0, -1)
        transactions = list(
            map(self._add_metadata, self._parser.get_transactions(accounts))
        )
        self._report_progress("transactions", 0, len(transactions))
        inserted = self._bulk_insert_transactions(
            transactions, self._parser.get_date_range()
        )
        self._report_progress("transactions", len(inserted), len(transactions))

"""Service for parsing CAS statements."""

import datetime
from collections.abc import Iterable
from pathlib import Path

import casparser

from niveshpy.exceptions import InvalidInputError, OperationError
from niveshpy.models.account import AccountCreate, AccountPublic
from niveshpy.models.parser import ParserInfo
from niveshpy.models.security import (
    SecurityCategory,
    SecurityCreate,
    SecurityType,
)
from niveshpy.models.transaction import (
    TransactionCreate,
    TransactionType,
)


class CASParser:
    """Service for managing CAS statements."""

    def __init__(self, file_path: str, password: str | None = None):
        """Initialize the CAS Parser with a file path."""
        self.data = casparser.read_cas_pdf(file_path, password)
        if not isinstance(self.data, casparser.CASData):
            raise InvalidInputError(
                file_path, "Only CAMS and Kfintech CAS statements are supported."
            )

        if self.data.cas_type != "DETAILED":
            raise InvalidInputError(
                file_path, "Only DETAILED CAS statements are supported."
            )

    def get_date_range(self) -> tuple[datetime.date, datetime.date]:
        """Get the date range of the CAS data."""
        try:
            start_date = datetime.datetime.strptime(
                self.data.statement_period.from_, "%d-%b-%Y"
            ).date()
            end_date = datetime.datetime.strptime(
                self.data.statement_period.to, "%d-%b-%Y"
            ).date()
        except ValueError as ve:
            raise OperationError(
                "Failed to parse statement period dates from CAS data."
            ) from ve
        return start_date, end_date

    def get_accounts(self) -> list[AccountCreate]:
        """Get the list of folios as accounts from the CAS data."""
        return [
            AccountCreate(
                name=folio_data.folio,
                institution=folio_data.amc,
                properties={"source": "cas"},
            )
            for folio_data in self.data.folios
        ]

    def get_securities(self) -> Iterable[SecurityCreate]:
        """Get the list of securities from the CAS data."""
        securities = set()
        for folio in self.data.folios:
            for scheme in folio.schemes:
                if scheme.amfi not in securities:
                    securities.add(scheme.amfi)
                    yield SecurityCreate(
                        key=scheme.amfi,
                        name=scheme.scheme,
                        type=SecurityType.MUTUAL_FUND,
                        category=SecurityCategory(scheme.type.lower())
                        if scheme.type in ("EQUITY", "DEBT")
                        else SecurityCategory.OTHER,
                        properties={"source": "cas", "isin": scheme.isin},
                    )

    def get_transactions(
        self, accounts: Iterable[AccountPublic]
    ) -> Iterable[TransactionCreate]:
        """Get the list of transactions from the CAS data."""
        accounts_map = {(acc.name, acc.institution): acc.id for acc in accounts}
        for folio in self.data.folios:
            account_id = accounts_map.get((folio.folio, folio.amc))
            if account_id is None:
                raise OperationError(
                    f"Account for folio {folio.folio} and AMC {folio.amc} not found."
                )
            for scheme in folio.schemes:
                for transaction in scheme.transactions:
                    if transaction.type in (
                        "DIVIDEND_REINVEST",
                        "PURCHASE",
                        "PURCHASE_SIP",
                        "REVERSAL",
                        "SWITCH_IN",
                        "SWITCH_IN_MERGER",
                    ):
                        txn_type = TransactionType.PURCHASE
                    elif transaction.type in (
                        "REDEMPTION",
                        "SWITCH_OUT",
                        "SWITCH_OUT_MERGER",
                    ):
                        txn_type = TransactionType.SALE
                    else:
                        continue  # Skip unknown transaction types

                    txn = TransactionCreate(
                        transaction_date=transaction.date,
                        type=txn_type,
                        description=transaction.description,
                        amount=transaction.amount,
                        units=transaction.units,
                        security_key=scheme.amfi,
                        account_id=account_id,
                        properties={"source": "cas", "original_type": transaction.type},
                    )
                    yield txn


class CASParserFactory:
    """Factory for creating CASParser instances."""

    @classmethod
    def get_parser_info(cls) -> ParserInfo:
        """Get information about the CAS parser."""
        return ParserInfo(
            name="CAS Parser",
            description="Parser for CAMS and Kfintech Consolidated Account Statements (CAS).",
            file_extensions=[".pdf"],
            password_required=True,
        )

    @classmethod
    def create_parser(
        cls, file_path: Path | str, password: str | None = None
    ) -> CASParser:
        """Create a CASParser instance."""
        if isinstance(file_path, Path):
            file_path = file_path.as_posix()
        return CASParser(file_path, password)

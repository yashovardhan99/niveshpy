"""Service for parsing CAS statements."""

from collections.abc import Generator
from pathlib import Path
import casparser  # type: ignore

from niveshpy.models.account import AccountWrite
from niveshpy.models.security import Security, SecurityCategory, SecurityType
import polars as pl

from niveshpy.models.transaction import TransactionType


class CASParser:
    """Service for managing CAS statements."""

    def __init__(self, file_path: Path | str, password: str | None = None):
        """Initialize the CAS Parser with a file path."""
        self.data = casparser.read_cas_pdf(file_path, password)
        if not isinstance(self.data, casparser.CASData):
            raise ValueError("Only CAMS and Kfintech CAS statements are supported.")

        if self.data.cas_type != "DETAILED":
            raise ValueError("Only DETAILED CAS statements are supported.")

    def get_accounts(self) -> list[AccountWrite]:
        """Get the list of folios as accounts from the CAS data."""
        return [
            AccountWrite(folio_data.folio, folio_data.amc)
            for folio_data in self.data.folios
        ]

    def get_securities(self) -> Generator[Security, None, None]:
        """Get the list of securities from the CAS data."""
        securities = set()
        for folio in self.data.folios:
            for scheme in folio.schemes:
                if scheme.amfi not in securities:
                    securities.add(scheme.amfi)
                    yield Security(
                        scheme.amfi,
                        scheme.scheme,
                        SecurityType.MUTUAL_FUND,
                        SecurityCategory(scheme.type.lower())
                        if scheme.type in ("EQUITY", "DEBT")
                        else SecurityCategory.OTHER,
                    )

    def get_transactions(self) -> pl.DataFrame:
        """Get the list of transactions from the CAS data."""
        transactions = []
        for folio in self.data.folios:
            for scheme in folio.schemes:
                transactions.append(
                    pl.from_dicts(scheme.transactions).with_columns(
                        pl.lit(scheme.amfi).alias("security_key"),
                        pl.lit(folio.folio).alias("account_name"),
                        pl.lit(folio.amc).alias("account_institution"),
                    )
                )

        df = pl.concat(transactions) if transactions else pl.DataFrame()
        df = df.select(
            pl.col("date").cast(pl.Date).alias("transaction_date"),
            pl.when(
                pl.col("type").is_in(
                    [
                        "DIVIDEND_REINVEST",
                        "PURCHASE",
                        "PURCHASE_SIP",
                        "REVERSAL",
                        "SWITCH_IN",
                        "SWITCH_IN_MERGER",
                    ],
                )
            )
            .then(pl.lit(TransactionType.PURCHASE))
            .when(
                pl.col("type").is_in(
                    [
                        "REDEMPTION",
                        "SWITCH_OUT",
                        "SWITCH_OUT_MERGER",
                    ],
                )
            )
            .then(pl.lit(TransactionType.SALE))
            .otherwise(pl.lit(None))
            .alias("type"),
            pl.col("description"),
            pl.col("amount").cast(pl.Decimal(24, 2)),
            pl.col("units").cast(pl.Decimal(24, 3)),
            pl.col("security_key"),
            pl.col("account_name"),
            pl.col("account_institution"),
        ).filter(pl.col("type").is_not_null())
        return df

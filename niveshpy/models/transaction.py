"""Models for financial transactions."""

from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from enum import StrEnum, auto
import polars as pl


class TransactionType(StrEnum):
    """Enum for transaction types."""

    PURCHASE = auto()
    SALE = auto()


@dataclass
class Transaction:
    """Model for transaction data."""

    transaction_date: date
    type: TransactionType
    description: str
    amount: Decimal
    units: Decimal
    security_key: str
    account_key: str

    @staticmethod
    def get_polars_schema_overrides() -> pl.Schema:
        """Get the Polars schema for the Transaction model."""
        return pl.Schema(
            {
                "amount": pl.Decimal(24, 2),
                "units": pl.Decimal(24, 3),
            }
        )

"""Models for financial transactions."""

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime
from enum import StrEnum, auto


class TransactionType(StrEnum):
    """Enum for transaction types."""

    PURCHASE = auto()
    SALE = auto()

    @staticmethod
    def rich_format(security_type: str) -> str:
        """Format the security type for display."""
        return {
            TransactionType.PURCHASE.value: "[green]Purchase",
            TransactionType.SALE.value: "[red]Sale",
        }.get(security_type, "[reverse]Unknown")


@dataclass
class TransactionRead:
    """Model for reading transaction data."""

    id: int
    transaction_date: date
    type: TransactionType
    description: str
    amount: Decimal
    units: Decimal
    security: str  # Formatted as "name (key)"
    account: str  # Formatted as "name (institution)"
    created: datetime
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def rich_format_map() -> list[str | Callable[[str], str] | None]:
        """Get a list of formatting styles for rich table display."""
        return [
            "dim",  # id
            "cyan",  # date
            TransactionType.rich_format,  # type
            None,  # description
            "bold",  # amount
            "yellow",  # units
            None,  # security
            "dim",  # account
            "dim",  # created
            "dim",  # metadata
        ]


@dataclass
class TransactionWrite:
    """Model for transaction data."""

    transaction_date: date
    type: TransactionType
    description: str
    amount: Decimal
    units: Decimal
    security_key: str
    account_id: int
    created: datetime = datetime.now()
    metadata: dict[str, str] = field(default_factory=dict)

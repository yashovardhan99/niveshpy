"""Models for securities."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from niveshpy.cli.utils import output


class SecurityType(StrEnum):
    """Enum for security types."""

    STOCK = auto()
    BOND = auto()
    ETF = auto()
    MUTUAL_FUND = auto()
    OTHER = auto()

    @staticmethod
    def rich_format(security_type: str) -> str:
        """Format the security type for display."""
        return {
            SecurityType.STOCK.value: "[white]Stock",
            SecurityType.BOND.value: "[cyan]Bond",
            SecurityType.ETF.value: "[yellow]ETF",
            SecurityType.MUTUAL_FUND.value: "[green]Mutual Fund",
            SecurityType.OTHER.value: "[dim]Other",
        }.get(security_type, "[reverse]Unknown")


class SecurityCategory(StrEnum):
    """Enum for security categories."""

    EQUITY = auto()
    DEBT = auto()
    COMMODITY = auto()
    REAL_ESTATE = auto()
    OTHER = auto()

    @staticmethod
    def rich_format(category: str) -> str:
        """Format the security category for display."""
        return {
            SecurityCategory.EQUITY.value: "[white]Equity",
            SecurityCategory.DEBT.value: "[cyan]Debt",
            SecurityCategory.COMMODITY.value: "[yellow]Commodity",
            SecurityCategory.REAL_ESTATE.value: "[bright_red]Real Estate",
            SecurityCategory.OTHER.value: "[dim]Other",
        }.get(category, "[reverse]Unknown")


@dataclass
class SecurityRead:
    """Model for security data."""

    key: str
    name: str
    type: SecurityType
    category: SecurityCategory
    created: datetime = datetime.now()
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def rich_format_map() -> "output.FormatMap":
        """Get a list of formatting styles for rich table display."""
        return [
            "green",
            "bold",
            SecurityType.rich_format,
            SecurityCategory.rich_format,
            "dim",
            "dim",
        ]


@dataclass
class SecurityWrite:
    """Model for creating or updating security data."""

    key: str
    name: str
    type: SecurityType
    category: SecurityCategory
    metadata: dict[str, str] = field(default_factory=dict)

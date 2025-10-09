"""Models for securities."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, auto


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
    OTHER = auto()

    @staticmethod
    def rich_format(category: str) -> str:
        """Format the security category for display."""
        return {
            SecurityCategory.EQUITY.value: "[white]Equity",
            SecurityCategory.DEBT.value: "[cyan]Debt",
            SecurityCategory.COMMODITY.value: "[yellow]Commodity",
            SecurityCategory.OTHER.value: "[dim]Other",
        }.get(category, "[reverse]Unknown")


@dataclass
class Security:
    """Model for security data."""

    key: str
    name: str
    type: SecurityType
    category: SecurityCategory

    @staticmethod
    def rich_format_map() -> list[str | Callable[[str], str] | None]:
        """Get a list of formatting styles for rich table display."""
        return ["green", "bold", SecurityType.rich_format, SecurityCategory.rich_format]

"""Models for securities."""

from dataclasses import dataclass
from enum import StrEnum, auto


class SecurityType(StrEnum):
    """Enum for security types."""

    STOCK = auto()
    BOND = auto()
    ETF = auto()
    MUTUAL_FUND = auto()
    OTHER = auto()


class SecurityCategory(StrEnum):
    """Enum for security categories."""

    EQUITY = auto()
    DEBT = auto()
    COMMODITY = auto()
    OTHER = auto()


@dataclass
class Security:
    """Model for security data."""

    key: str
    name: str
    type: SecurityType
    category: SecurityCategory

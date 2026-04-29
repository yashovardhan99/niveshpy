"""Models for securities."""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum, auto
from typing import Any

from attrs import field, frozen


class SecurityType(StrEnum):
    """Enum for security types."""

    STOCK = auto()
    """Security type representing stocks."""
    BOND = auto()
    """Security type representing bonds."""
    ETF = auto()
    """Security type representing exchange-traded funds."""
    MUTUAL_FUND = auto()
    """Security type representing mutual funds."""
    OTHER = auto()
    """Security type representing other types of securities."""


class SecurityCategory(StrEnum):
    """Enum for security categories."""

    EQUITY = auto()
    """Security category representing equity."""
    DEBT = auto()
    """Security category representing debt."""
    COMMODITY = auto()
    """Security category representing commodities."""
    REAL_ESTATE = auto()
    """Security category representing real estate."""
    OTHER = auto()
    """Security category representing other categories."""


@frozen
class SecurityCreate:
    """Model for creating a new security.

    Attributes:
        key (str): Unique key identifying the security.
        name (str): Name of the security.
        type (SecurityType): Type of the security.
        category (SecurityCategory): Category of the security.
        properties (dict[str, Any], optional): Additional properties of the security.
            Defaults to an empty dictionary.
    """

    key: str
    name: str
    type: SecurityType
    category: SecurityCategory
    properties: Mapping[str, Any] = field(factory=dict)


@frozen
class SecurityPublic:
    """Public model for a security.

    Attributes:
        key (str): Unique key identifying the security.
        name (str): Name of the security.
        type (SecurityType): Type of the security.
        category (SecurityCategory): Category of the security.
        properties (dict[str, Any]): Additional properties of the security.
        created (datetime): Timestamp when the security was created.
    """

    key: str
    name: str
    type: SecurityType
    category: SecurityCategory
    properties: Mapping[str, Any]
    created: datetime

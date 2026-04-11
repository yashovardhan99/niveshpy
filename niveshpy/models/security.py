"""Models for securities."""

from datetime import datetime
from enum import StrEnum, auto
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel


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


class SecurityBase(SQLModel):
    """Base model for securities.

    Attributes:
        key (str): Unique key identifying the security.
        name (str): Name of the security.
        type (SecurityType): Type of the security.
        category (SecurityCategory): Category of the security.
        properties (dict[str, Any], optional): Additional properties of the security.
            Defaults to an empty dictionary.
    """

    key: str = Field(primary_key=True)
    name: str = Field()
    type: SecurityType = Field()
    category: SecurityCategory = Field()
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    def __init_subclass__(cls, **kwargs):
        """Ensure subclasses inherit schema extra metadata."""
        return super().__init_subclass__(**kwargs)


class SecurityCreate(SecurityBase):
    """Model for creating a new security.

    Attributes:
        key (str): Unique key identifying the security.
        name (str): Name of the security.
        type (SecurityType): Type of the security.
        category (SecurityCategory): Category of the security.
        properties (dict[str, Any], optional): Additional properties of the security.
            Defaults to an empty dictionary.
    """


class Security(SecurityBase, table=True):
    """Database model for securities.

    Attributes:
        key (str): Unique key identifying the security.
        name (str): Name of the security.
        type (SecurityType): Type of the security.
        category (SecurityCategory): Category of the security.
        properties (dict[str, Any]): Additional properties of the security.
        created (datetime): Timestamp when the security was created.
    """

    created: datetime = Field(default_factory=datetime.now)

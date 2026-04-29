"""SQLite models for NiveshPy."""

import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import (
    JSON,
    NUMERIC,
    Column,
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
)

from niveshpy.models.security import SecurityCategory, SecurityPublic, SecurityType


class Account(SQLModel, table=True):
    """Database model for investment accounts.

    Attributes:
        id (int | None): Primary key ID of the account. None if not yet stored in DB.
        name (str): Name of the account.
        institution (str): Financial institution managing the account.
        properties (dict[str, Any]): Additional properties of the account.
        created_at (datetime): Timestamp when the account was created.
    """

    __table_args__ = (
        UniqueConstraint("name", "institution", name="uix_name_institution"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str
    institution: str
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)


class Security(SQLModel, table=True):
    """Database model for securities.

    Attributes:
        key (str): Unique key identifying the security.
        name (str): Name of the security.
        type (SecurityType): Type of the security.
        category (SecurityCategory): Category of the security.
        properties (dict[str, Any]): Additional properties of the security.
        created (datetime): Timestamp when the security was created.
    """

    key: str = Field(primary_key=True)
    name: str = Field()
    type: SecurityType = Field()
    category: SecurityCategory = Field()
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created: datetime.datetime = Field(default_factory=datetime.datetime.now)

    def to_public(self) -> SecurityPublic:
        """Convert a Security database model to a SecurityPublic domain model."""
        return SecurityPublic(
            key=self.key,
            name=self.name,
            type=self.type,
            category=self.category,
            properties=self.properties,
            created=self.created,
        )


class Price(SQLModel, table=True):
    """Database model for price data.

    Attributes:
        security_key (str): Foreign key to the associated security.
        security (Security): Related security object.
        date (datetime.date): Date of the price data.
        open (Decimal): Opening price.
        high (Decimal): Highest price.
        low (Decimal): Lowest price.
        close (Decimal): Closing price.
        properties (dict[str, Any]): Additional properties of the price data.
        created (datetime.datetime): Timestamp when the price data was created.
    """

    security_key: str = Field(foreign_key="security.key", primary_key=True)
    security: Security = Relationship()
    date: datetime.date = Field(primary_key=True)
    open: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    high: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    low: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    close: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created: datetime.datetime = Field(
        default_factory=datetime.datetime.now, title="Created"
    )

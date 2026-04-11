"""Price data models."""

import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import JSON, NUMERIC, Column, Field, Relationship, SQLModel

from niveshpy.models.security import Security


class PriceBase(SQLModel):
    """Base model for price data.

    Attributes:
        security_key (str): Foreign key to the associated security.
        date (datetime.date): Date of the price data.
        open (Decimal): Opening price.
        high (Decimal): Highest price.
        low (Decimal): Lowest price.
        close (Decimal): Closing price.
        properties (dict[str, Any], optional): Additional properties of the price data.
            Defaults to an empty dictionary.
    """

    security_key: str = Field(foreign_key="security.key", primary_key=True)
    date: datetime.date = Field(primary_key=True)
    open: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    high: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    low: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    close: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    def __init_subclass__(cls, **kwargs):
        """Ensure subclasses inherit schema extra metadata."""
        return super().__init_subclass__(**kwargs)


class PriceCreate(PriceBase):
    """Model for creating price data.

    Attributes:
        security_key (str): Foreign key to the associated security.
        date (datetime.date): Date of the price data.
        open (Decimal): Opening price.
        high (Decimal): Highest price.
        low (Decimal): Lowest price.
        close (Decimal): Closing price.
        properties (dict[str, Any], optional): Additional properties of the price data.
            Defaults to an empty dictionary.
    """


class Price(PriceBase, table=True):
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

    security: Security = Relationship()
    created: datetime.datetime = Field(
        default_factory=datetime.datetime.now, title="Created"
    )


class PricePublic(PriceBase):
    """Public model for price data exposure.

    Attributes:
        security_key (str): Foreign key to the associated security.
        date (datetime.date): Date of the price data.
        open (Decimal): Opening price.
        high (Decimal): Highest price.
        low (Decimal): Lowest price.
        close (Decimal): Closing price.
        properties (dict[str, Any]): Additional properties of the price data.
        created (datetime.datetime): Timestamp when the price data was created.
    """

    created: datetime.datetime = Field(title="Created")


class PricePublicWithRelations(PricePublic):
    """Public model for price data with related security.

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

    security: Security = Field(title="Security")

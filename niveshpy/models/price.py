"""Price data models."""

import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field as PydanticField
from pydantic import field_validator
from sqlmodel import JSON, NUMERIC, Column, Field, Relationship, SQLModel

from niveshpy.core.query import ast
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

    security_key: str = Field(
        foreign_key="security.key",
        primary_key=True,
        schema_extra={"json_schema_extra": {"order": 0, "hidden": True}},
    )
    date: datetime.date = Field(
        primary_key=True,
        schema_extra={"json_schema_extra": {"order": 1, "style": "cyan"}},
    )
    open: Decimal = Field(
        sa_column=Column(NUMERIC(24, 4)),
        schema_extra={"json_schema_extra": {"order": 2, "justify": "right"}},
    )
    high: Decimal = Field(
        sa_column=Column(NUMERIC(24, 4)),
        schema_extra={
            "json_schema_extra": {"order": 3, "style": "green", "justify": "right"}
        },
    )
    low: Decimal = Field(
        sa_column=Column(NUMERIC(24, 4)),
        schema_extra={
            "json_schema_extra": {"order": 4, "style": "red", "justify": "right"}
        },
    )
    close: Decimal = Field(
        sa_column=Column(NUMERIC(24, 4)),
        schema_extra={
            "json_schema_extra": {"order": 5, "style": "bold", "justify": "right"}
        },
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        schema_extra={"json_schema_extra": {"style": "dim", "order": 7}},
    )

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

    created: datetime.datetime = Field(
        title="Created",
        schema_extra={"json_schema_extra": {"style": "dim", "order": 6}},
    )


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

    security: Security = Field(
        title="Security",
        schema_extra={"json_schema_extra": {"order": 0}},
    )


class PriceDisplay(PricePublic):
    """Model for displaying price data with related info.

    Attributes:
        security (str): Formatted security information.
        date (datetime.date): Date of the price data.
        open (Decimal): Opening price.
        high (Decimal): Highest price.
        low (Decimal): Lowest price.
        close (Decimal): Closing price.
        properties (dict[str, Any]): Additional properties of the price data.
        created (datetime.datetime): Timestamp when the price data was created.
    """

    security: str = PydanticField(
        json_schema_extra={"order": 0},
    )

    @field_validator("security", mode="before", json_schema_input_type=str | Security)
    def format_security(cls, value: str | Security) -> str:
        """Format the security field for display."""
        if isinstance(value, Security):
            return f"{value.name} ({value.key})"
        return value


PRICE_COLUMN_MAPPING: dict[ast.Field, list] = {
    ast.Field.DATE: [Price.date],
    ast.Field.SECURITY: [
        Security.key,
        Security.name,
        Security.type,
        Security.category,
    ],
}

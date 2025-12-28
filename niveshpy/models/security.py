"""Models for securities."""

from datetime import datetime
from enum import StrEnum, auto
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel

from niveshpy.core.query import ast


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
    REAL_ESTATE = auto()
    OTHER = auto()


type_format_map = {
    SecurityType.STOCK.value: "[white]Stock",
    SecurityType.BOND.value: "[cyan]Bond",
    SecurityType.ETF.value: "[yellow]ETF",
    SecurityType.MUTUAL_FUND.value: "[green]Mutual Fund",
    SecurityType.OTHER.value: "[dim]Other",
}

category_format_map = {
    SecurityCategory.EQUITY.value: "[white]Equity",
    SecurityCategory.DEBT.value: "[cyan]Debt",
    SecurityCategory.COMMODITY.value: "[yellow]Commodity",
    SecurityCategory.REAL_ESTATE.value: "[bright_red]Real Estate",
    SecurityCategory.OTHER.value: "[dim]Other",
}


class SecurityBase(SQLModel):
    """Base model for securities."""

    key: str = Field(
        primary_key=True,
        schema_extra={
            "json_schema_extra": {"style": "green", "order": 1, "justify": "right"}
        },
    )
    name: str = Field(schema_extra={"json_schema_extra": {"style": "bold", "order": 2}})
    type: SecurityType = Field(
        schema_extra={
            "json_schema_extra": {
                "order": 3,
                "formatter": lambda type: type_format_map.get(type, "[reverse]Unknown"),
            }
        }
    )
    category: SecurityCategory = Field(
        schema_extra={
            "json_schema_extra": {
                "order": 4,
                "formatter": lambda category: category_format_map.get(
                    category, "[reverse]Unknown"
                ),
            }
        }
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        schema_extra={"json_schema_extra": {"style": "dim", "order": 6}},
    )

    def __init_subclass__(cls, **kwargs):
        """Ensure subclasses inherit schema extra metadata."""
        return super().__init_subclass__(**kwargs)


class SecurityCreate(SecurityBase):
    """Model for creating a new security."""


class Security(SecurityBase, table=True):
    """Database model for securities."""

    created: datetime = Field(
        default_factory=datetime.now,
        schema_extra={"json_schema_extra": {"style": "dim", "order": 5}},
    )


SECURITY_COLUMN_MAPPING: dict[ast.Field, list[str]] = {
    ast.Field.SECURITY: ["key", "name"],
    ast.Field.TYPE: ["type", "category"],
}

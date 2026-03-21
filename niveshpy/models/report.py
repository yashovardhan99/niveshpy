"""Reports related models."""

import datetime
import decimal

from pydantic import BaseModel, Field

from niveshpy.core.query import ast
from niveshpy.exceptions import OperationError
from niveshpy.models.account import Account
from niveshpy.models.security import (
    Security,
    SecurityCategory,
    SecurityType,
    category_format_map,
    type_format_map,
)

# Holdings


class HoldingBase(BaseModel):
    """Base model for holding data."""

    date: datetime.date = Field(
        ...,
        json_schema_extra={
            "style": "cyan",
            "order": 3,
            "max_width": 14,
            "no_wrap": True,
        },
    )
    units: decimal.Decimal = Field(
        ...,
        json_schema_extra={
            "style": "green",
            "justify": "right",
            "order": 4,
            "max_width": 20,
            "no_wrap": True,
        },
    )
    amount: decimal.Decimal = Field(
        ...,
        json_schema_extra={
            "style": "bold",
            "justify": "right",
            "order": 5,
            "max_width": 20,
            "no_wrap": True,
        },
    )
    invested: decimal.Decimal | None = Field(
        default=None,
        json_schema_extra={
            "justify": "right",
            "order": 6,
            "max_width": 20,
            "no_wrap": True,
        },
    )
    gains: decimal.Decimal | None = Field(
        default=None,
        json_schema_extra={
            "style": "bold green",
            "justify": "right",
            "order": 7,
            "max_width": 20,
            "no_wrap": True,
        },
    )


class Holding(HoldingBase):
    """Model representing holding data for reports."""

    account: Account = Field(...)
    security: Security = Field(...)


class HoldingDisplay(HoldingBase):
    """Model representing holding data for display in reports."""

    account: str = Field(
        ..., json_schema_extra={"style": "dim", "order": 1, "max_width": 30}
    )
    security: str = Field(..., json_schema_extra={"order": 2})

    @classmethod
    def from_holding(cls, holding: Holding) -> "HoldingDisplay":
        """Create HoldingDisplay from Holding model."""
        return cls(
            account=f"{holding.account.name} ({holding.account.institution})",
            security=f"{holding.security.name} ({holding.security.key})",
            date=holding.date,
            units=holding.units,
            amount=holding.amount,
            invested=holding.invested,
            gains=holding.gains,
        )


class HoldingExport(HoldingBase):
    """Model representing holding data for csv export."""

    account: int
    security: str

    @classmethod
    def from_holding(cls, holding: Holding) -> "HoldingExport":
        """Create HoldingExport from Holding model."""
        if holding.account.id is None:
            raise OperationError("Account ID is required for export.")
        return cls(
            account=holding.account.id,
            security=holding.security.key,
            date=holding.date,
            units=holding.units,
            amount=holding.amount,
            invested=holding.invested,
            gains=holding.gains,
        )


HOLDING_COLUMN_MAPPINGS_TXN: dict[ast.Field, list] = {
    ast.Field.SECURITY: [Security.key, Security.name, Security.category, Security.type],
    ast.Field.ACCOUNT: [Account.name, Account.institution],
}
HOLDING_COLUMN_MAPPINGS_PRICE: dict[ast.Field, list] = {
    ast.Field.SECURITY: [Security.key, Security.name, Security.category, Security.type],
}

# Portfolio Totals


class PortfolioTotals(BaseModel):
    """Portfolio-level aggregate totals."""

    total_current_value: decimal.Decimal
    total_invested: decimal.Decimal | None
    total_gains: decimal.Decimal | None
    gains_percentage: decimal.Decimal | None


# Allocations


class AllocationBase(BaseModel):
    """Base model for allocation data."""

    date: datetime.date = Field(
        ...,
        json_schema_extra={
            "style": "cyan",
            "order": 3,
            "max_width": 14,
            "no_wrap": True,
        },
    )
    amount: decimal.Decimal = Field(
        ...,
        json_schema_extra={
            "justify": "right",
            "order": 4,
            "max_width": 20,
            "no_wrap": True,
        },
    )
    allocation: decimal.Decimal = Field(
        ...,
        json_schema_extra={
            "style": "green",
            "justify": "right",
            "order": 5,
            "max_width": 10,
            "no_wrap": True,
            "formatter": lambda x: f"{decimal.Decimal(x):.2%}",  # type: ignore
        },
    )


class AllocationByType(AllocationBase):
    """Model representing allocation by security type."""

    security_type: SecurityType = Field(
        ...,
        json_schema_extra={
            "order": 1,
            "max_width": 30,
            "formatter": lambda stype: type_format_map.get(stype, "[reverse]Unknown"),  # type: ignore
        },
        title="Type",
    )


class AllocationByCategory(AllocationBase):
    """Model representing allocation by security category."""

    security_category: SecurityCategory = Field(
        ...,
        json_schema_extra={
            "order": 1,
            "max_width": 30,
            "formatter": lambda category: category_format_map.get(  # type: ignore
                category, "[reverse]Unknown"
            ),
        },
        title="Category",
    )


class Allocation(AllocationByType, AllocationByCategory):
    """Model representing allocation data for reports."""


# Performance


class PerformanceDisplay(BaseModel):
    """Display model for portfolio performance metrics."""

    total_current_value: decimal.Decimal = Field(
        ...,
        title="Total Current Value",
        json_schema_extra={
            "order": 1,
            "justify": "right",
            "style": "bold",
            "no_wrap": True,
        },
    )
    total_invested: decimal.Decimal | None = Field(
        default=None,
        title="Total Invested",
        json_schema_extra={
            "order": 2,
            "justify": "right",
            "no_wrap": True,
            "formatter": lambda x: x or "N/A",  # type: ignore
        },
    )
    absolute_gains: decimal.Decimal | None = Field(
        default=None,
        title="Absolute Gains",
        json_schema_extra={
            "order": 3,
            "justify": "right",
            "style": "bold green",
            "no_wrap": True,
            "formatter": lambda x: x or "N/A",  # type: ignore
        },
    )
    absolute_gains_pct: decimal.Decimal | None = Field(
        default=None,
        title="Absolute Gains %",
        json_schema_extra={
            "order": 4,
            "justify": "right",
            "no_wrap": True,
            "formatter": lambda x: f"{decimal.Decimal(x):.2%}" if x else "N/A",  # type: ignore
        },
    )
    xirr: decimal.Decimal | None = Field(
        default=None,
        title="XIRR (Annualized)",
        json_schema_extra={
            "order": 5,
            "justify": "right",
            "style": "bold",
            "no_wrap": True,
            "formatter": lambda x: f"{decimal.Decimal(x):.2%}" if x else "N/A",  # type: ignore
        },
    )

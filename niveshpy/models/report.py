"""Reports related models."""

import datetime
import decimal
from collections.abc import Sequence

from pydantic import BaseModel, Field

from niveshpy.cli.utils.formatters import format_percentage
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
            "style": "dim",
            "justify": "right",
            "order": 4,
            "max_width": 20,
            "no_wrap": True,
        },
    )
    invested: decimal.Decimal | None = Field(
        default=None,
        json_schema_extra={
            "justify": "right",
            "order": 5,
            "style": "dim",
            "max_width": 20,
            "no_wrap": True,
        },
    )
    amount: decimal.Decimal = Field(
        ...,
        title="Current Value",
        json_schema_extra={
            "style": "bold",
            "justify": "right",
            "order": 6,
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
    xirr: decimal.Decimal | None = None
    last_updated: datetime.date | None = None


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
            "formatter": format_percentage,  # type: ignore
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


class PerformanceHoldingBase(BaseModel):
    """Base model for per-holding performance data."""

    date: datetime.date | None = Field(
        ...,
        json_schema_extra={
            "style": "cyan",
            "order": 2,
            "max_width": 14,
            "no_wrap": True,
        },
    )

    current_value: decimal.Decimal = Field(
        ...,
        title="Current Value",
        json_schema_extra={
            "order": 3,
            "justify": "right",
            "no_wrap": True,
        },
    )
    invested: decimal.Decimal | None = Field(
        default=None,
        json_schema_extra={
            "order": 4,
            "justify": "right",
            "style": "dim",
            "no_wrap": True,
        },
    )
    gains: decimal.Decimal | None = Field(
        default=None,
        json_schema_extra={
            "order": 5,
            "justify": "right",
            "no_wrap": True,
        },
    )
    gains_pct: decimal.Decimal | None = Field(
        default=None,
        title="Gains %",
        json_schema_extra={
            "order": 6,
            "justify": "right",
            "no_wrap": True,
            "formatter": format_percentage,  # type: ignore
        },
    )
    xirr: decimal.Decimal | None = Field(
        default=None,
        title="XIRR",
        json_schema_extra={
            "order": 7,
            "justify": "right",
            "style": "bold",
            "no_wrap": True,
            "formatter": format_percentage,  # type: ignore
        },
    )


def _compute_holding_gains(
    amount: decimal.Decimal,
    invested: decimal.Decimal | None,
) -> tuple[decimal.Decimal | None, decimal.Decimal | None]:
    """Compute gains and gains percentage from amount and invested.

    Returns:
        Tuple of (gains, gains_pct) where either may be None.
    """
    if invested is None:
        return None, None
    gains = (amount - invested).quantize(decimal.Decimal("0.01"))
    gains_pct: decimal.Decimal | None = None
    if invested > 0:
        gains_pct = (gains / invested).quantize(decimal.Decimal("0.0001"))
    return gains, gains_pct


class PerformanceHolding(PerformanceHoldingBase):
    """Model representing per-holding performance data for reports."""

    account: Account = Field(...)
    security: Security = Field(...)

    @classmethod
    def from_holding(
        cls, holding: Holding, xirr: decimal.Decimal | None
    ) -> "PerformanceHolding":
        """Create PerformanceHolding from Holding and XIRR value."""
        gains, gains_pct = _compute_holding_gains(holding.amount, holding.invested)
        return cls(
            account=holding.account,
            security=holding.security,
            date=holding.date,
            current_value=holding.amount,
            invested=holding.invested,
            gains=gains,
            gains_pct=gains_pct,
            xirr=xirr,
        )


class PerformanceResult(BaseModel):
    """Result of portfolio performance computation."""

    holdings: list[PerformanceHolding]
    totals: PortfolioTotals


class SummaryResult(BaseModel):
    """Portfolio summary combining metrics, top holdings, and allocation."""

    as_of: datetime.date | None
    metrics: PortfolioTotals
    top_holdings: Sequence[PerformanceHolding]
    allocation: Sequence[AllocationByCategory]


class PerformanceHoldingDisplay(PerformanceHoldingBase):
    """Display model for per-holding performance in reports."""

    account: str = Field(
        ..., json_schema_extra={"style": "dim", "order": 0, "max_width": 20}
    )
    security: str = Field(..., json_schema_extra={"order": 1})

    @classmethod
    def from_holding(cls, holding: PerformanceHolding) -> "PerformanceHoldingDisplay":
        """Create PerformanceHoldingDisplay from PerformanceHolding."""
        return cls(
            account=f"{holding.account.name} ({holding.account.institution})",
            security=f"{holding.security.name} ({holding.security.key})",
            date=holding.date,
            current_value=holding.current_value,
            invested=holding.invested,
            gains=holding.gains,
            gains_pct=holding.gains_pct,
            xirr=holding.xirr,
        )


class PerformanceHoldingExport(PerformanceHoldingBase):
    """Export model for per-holding performance in CSV."""

    account: int = Field(..., json_schema_extra={"order": 1})
    security: str = Field(..., json_schema_extra={"order": 2})

    @classmethod
    def from_holding(cls, holding: PerformanceHolding) -> "PerformanceHoldingExport":
        """Create PerformanceHoldingExport from PerformanceHolding."""
        if holding.account.id is None:
            raise OperationError("Account ID is required for export.")
        return cls(
            account=holding.account.id,
            security=holding.security.key,
            date=holding.date,
            current_value=holding.current_value,
            invested=holding.invested,
            gains=holding.gains,
            gains_pct=holding.gains_pct,
            xirr=holding.xirr,
        )

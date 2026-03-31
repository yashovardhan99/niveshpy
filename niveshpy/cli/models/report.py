"""Module for report-related data models used in the CLI."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self

from niveshpy.cli.models.account import AccountDisplay
from niveshpy.cli.models.security import (
    SecurityDisplay,
    _format_security_category,
    _format_security_type,
)
from niveshpy.cli.utils.formatters import format_date, format_decimal, format_percentage
from niveshpy.cli.utils.models import Column

if TYPE_CHECKING:
    from niveshpy.models.report import (
        Allocation,
        Holding,
        PerformanceHolding,
        PortfolioTotals,
        SummaryResult,
    )
    from niveshpy.models.security import SecurityCategory, SecurityType


def _format_account(account: AccountDisplay) -> str:
    return f"{account.name} ({account.institution})"


def _format_security(security: SecurityDisplay) -> str:
    return f"{security.name} ({security.key})"


@dataclass(slots=True, frozen=True)
class HoldingDisplay:
    """Data class for displaying holding information in CLI output."""

    account: AccountDisplay
    security: SecurityDisplay
    date: datetime.date
    units: Decimal
    invested: Decimal | None
    current: Decimal

    columns: ClassVar[Sequence[Column]] = [
        Column("account", style="dim", formatter=_format_account),
        Column("security", style="bold", formatter=_format_security),
        Column("date", style="cyan", formatter=format_date),
        Column("units", style="dim", formatter=format_decimal, justify="right"),
        Column("invested", style="dim", formatter=format_decimal, justify="right"),
        Column("current", style="bold", formatter=format_decimal, justify="right"),
    ]
    csv_fields: ClassVar[Sequence[str]] = [
        "account",
        "security",
        "date",
        "units",
        "invested",
        "current",
    ]

    @classmethod
    def from_domain(cls, holding: Holding) -> "HoldingDisplay":
        """Create HoldingDisplay from Holding model."""
        return cls(
            account=AccountDisplay.from_domain(holding.account),
            security=SecurityDisplay.from_domain(holding.security),
            date=holding.date,
            units=holding.units,
            invested=holding.invested,
            current=holding.amount,
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the HoldingDisplay instance to a JSON-serializable dictionary."""
        return {
            "account": self.account.to_json_dict(),
            "security": self.security.to_json_dict(),
            "date": self.date.isoformat(),
            "units": str(self.units),
            "invested": str(self.invested) if self.invested is not None else None,
            "current": str(self.current),
        }

    def to_csv_dict(self) -> dict[str, Any]:
        """Convert the AccountDisplay instance to a dictionary suitable for CSV output."""
        return {
            "account": self.account.id,
            "security": self.security.key,
            "date": self.date.isoformat(),
            "units": self.units,
            "invested": self.invested,
            "current": self.current,
        }


@dataclass(slots=True, frozen=True)
class AllocationDisplay:
    """Data class for displaying allocation information in CLI output."""

    date: datetime.date
    amount: Decimal
    allocation: Decimal
    security_type: SecurityType | None
    security_category: SecurityCategory | None

    _base_columns: ClassVar[Sequence[Column]] = [
        Column("date", style="cyan", formatter=format_date),
        Column("amount", style="bold", formatter=format_decimal, justify="right"),
        Column(
            "allocation", style="bold", formatter=format_percentage, justify="right"
        ),
    ]
    _base_csv_fields: ClassVar[Sequence[str]] = ["date", "amount", "allocation"]

    def __post_init__(self) -> None:
        """Validate that at least one of security_type or security_category is provided."""
        if self.security_type is None and self.security_category is None:
            raise ValueError(
                "Either security_type or security_category must be provided."
            )

    @classmethod
    def from_domain(
        cls,
        allocation: Allocation,
    ) -> "AllocationDisplay":
        """Create an AllocationDisplay instance from a domain Allocation model."""
        return cls(
            date=allocation.date,
            amount=allocation.amount,
            allocation=allocation.allocation,
            security_type=allocation.security_type,
            security_category=allocation.security_category,
        )

    @classmethod
    def get_columns(
        cls, group_by: Literal["both", "type", "category"]
    ) -> Sequence[Column]:
        """Get the appropriate columns based on whether security type or category is used."""
        columns: list[Column] = []
        if group_by in ("both", "type"):
            columns.append(Column("security_type", formatter=_format_security_type))
        if group_by in ("both", "category"):
            columns.append(
                Column("security_category", formatter=_format_security_category)
            )
        columns.extend(cls._base_columns)
        return columns

    @classmethod
    def get_csv_fields(
        cls, group_by: Literal["both", "type", "category"]
    ) -> Sequence[str]:
        """Get the appropriate CSV fields based on whether security type or category is used."""
        fields: list[str] = []
        if group_by in ("both", "type"):
            fields.append("security_type")
        if group_by in ("both", "category"):
            fields.append("security_category")
        fields.extend(cls._base_csv_fields)
        return fields

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the AllocationDisplay instance to a JSON-serializable dictionary."""
        json_dict = {
            "date": self.date.isoformat(),
            "amount": str(self.amount),
            "allocation": str(self.allocation),
        }
        if self.security_type is not None:
            json_dict["security_type"] = self.security_type.value
        if self.security_category is not None:
            json_dict["security_category"] = self.security_category.value
        return json_dict

    def to_csv_dict(self) -> dict[str, Any]:
        """Convert the AllocationDisplay instance to a dictionary suitable for CSV output."""
        csv_dict = {
            "date": self.date.isoformat(),
            "amount": self.amount,
            "allocation": self.allocation,
        }
        if self.security_type is not None:
            csv_dict["security_type"] = self.security_type.value
        if self.security_category is not None:
            csv_dict["security_category"] = self.security_category.value
        return csv_dict


@dataclass(slots=True, frozen=True)
class PerformanceHoldingDisplay:
    """Data class for per-holding performance data used in reports."""

    account: AccountDisplay
    security: SecurityDisplay
    date: datetime.date
    current_value: Decimal
    invested: Decimal | None
    gains: Decimal | None
    gains_pct: Decimal | None
    xirr: Decimal | None

    columns: ClassVar[Sequence[Column]] = [
        Column("account", style="dim", formatter=_format_account),
        Column("security", style="bold", formatter=_format_security),
        Column("date", style="cyan", formatter=format_date),
        Column("current_value", formatter=format_decimal, justify="right"),
        Column("invested", style="dim", formatter=format_decimal, justify="right"),
        Column(
            "gains", name="Absolute Gains", formatter=format_decimal, justify="right"
        ),
        Column(
            "gains_pct", name="Gains (%)", formatter=format_percentage, justify="right"
        ),
        Column("xirr", name="XIRR (%)", formatter=format_percentage, justify="right"),
    ]
    csv_fields: ClassVar[Sequence[str]] = [
        "account",
        "security",
        "date",
        "current_value",
        "invested",
        "gains",
        "gains_pct",
        "xirr",
    ]

    @classmethod
    def from_domain(cls, holding: PerformanceHolding) -> Self:
        """Create PerformanceHoldingDisplay from PerformanceHolding model."""
        return cls(
            account=AccountDisplay.from_domain(holding.account),
            security=SecurityDisplay.from_domain(holding.security),
            date=holding.date,
            current_value=holding.current_value,
            invested=holding.invested,
            gains=holding.gains,
            gains_pct=holding.gains_pct,
            xirr=holding.xirr,
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the PerformanceHoldingDisplay instance to a JSON-serializable dictionary."""
        return {
            "account": self.account.to_json_dict(),
            "security": self.security.to_json_dict(),
            "date": self.date.isoformat(),
            "current_value": str(self.current_value),
            "invested": str(self.invested) if self.invested is not None else None,
            "gains": str(self.gains) if self.gains is not None else None,
            "gains_pct": str(self.gains_pct) if self.gains_pct is not None else None,
            "xirr": str(self.xirr) if self.xirr is not None else None,
        }

    def to_csv_dict(self) -> dict[str, Any]:
        """Convert the PerformanceHoldingDisplay instance to a dictionary suitable for CSV output."""
        return {
            "account": self.account.id,
            "security": self.security.key,
            "date": self.date.isoformat(),
            "current_value": self.current_value,
            "invested": self.invested,
            "gains": self.gains,
            "gains_pct": self.gains_pct,
            "xirr": self.xirr,
        }


@dataclass(slots=True)
class PortfolioTotalsDisplay:
    """Portfolio-level aggregate totals."""

    total_current_value: Decimal
    total_invested: Decimal | None
    total_gains: Decimal | None
    gains_percentage: Decimal | None
    xirr: Decimal | None = None
    last_updated: datetime.date | None = None

    @classmethod
    def from_domain(cls, totals: PortfolioTotals) -> Self:
        """Create PortfolioTotalsDisplay from PortfolioTotals domain model."""
        return cls(
            total_current_value=totals.total_current_value,
            total_invested=totals.total_invested,
            total_gains=totals.total_gains,
            gains_percentage=totals.gains_percentage,
            xirr=totals.xirr,
            last_updated=totals.last_updated,
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the PortfolioTotals instance to a JSON-serializable dictionary."""
        return {
            "total_current_value": str(self.total_current_value),
            "total_invested": str(self.total_invested)
            if self.total_invested is not None
            else None,
            "total_gains": str(self.total_gains)
            if self.total_gains is not None
            else None,
            "gains_percentage": str(self.gains_percentage)
            if self.gains_percentage is not None
            else None,
            "xirr": str(self.xirr) if self.xirr is not None else None,
            "last_updated": self.last_updated.isoformat()
            if self.last_updated
            else None,
        }


@dataclass(slots=True, frozen=True)
class SummaryResultDisplay:
    """Portfolio summary combining metrics, top holdings, and allocation."""

    date: datetime.date | None
    metrics: PortfolioTotalsDisplay
    top_holdings: Sequence[PerformanceHoldingDisplay]
    allocation: Sequence[AllocationDisplay]

    @classmethod
    def from_domain(
        cls,
        summary: SummaryResult,
    ) -> "SummaryResultDisplay":
        """Create SummaryResultDisplay from SummaryResult domain model."""
        return cls(
            date=summary.as_of,
            metrics=PortfolioTotalsDisplay.from_domain(summary.metrics),
            top_holdings=[
                PerformanceHoldingDisplay.from_domain(h) for h in summary.top_holdings
            ],
            allocation=[AllocationDisplay.from_domain(a) for a in summary.allocation],
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the SummaryResultDisplay instance to a JSON-serializable dictionary."""
        return {
            "date": self.date.isoformat() if self.date else None,
            "metrics": self.metrics.to_json_dict(),
            "top_holdings": [h.to_json_dict() for h in self.top_holdings],
            "allocation": [a.to_json_dict() for a in self.allocation],
        }

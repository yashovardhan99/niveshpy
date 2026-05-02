"""Module for report-related data models used in the CLI."""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, ClassVar, Self

from niveshpy.cli.models.account import AccountDisplay
from niveshpy.cli.models.security import SecurityDisplay
from niveshpy.cli.utils.formatters import (
    format_account,
    format_date,
    format_decimal,
    format_percentage,
    format_security,
)
from niveshpy.cli.utils.models import Column
from niveshpy.core.converter import get_json_converter
from niveshpy.models.report import (
    Allocation,
    PerformanceHolding,
    PortfolioTotals,
    SummaryResult,
)


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
        Column("account", style="dim", formatter=format_account),
        Column("security", style="bold", formatter=format_security),
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
    allocation: Sequence[Allocation]

    @classmethod
    def from_domain(
        cls,
        summary: SummaryResult,
    ) -> SummaryResultDisplay:
        """Create SummaryResultDisplay from SummaryResult domain model."""
        return cls(
            date=summary.as_of,
            metrics=PortfolioTotalsDisplay.from_domain(summary.metrics),
            top_holdings=[
                PerformanceHoldingDisplay.from_domain(h) for h in summary.top_holdings
            ],
            allocation=summary.allocation,
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the SummaryResultDisplay instance to a JSON-serializable dictionary."""
        c = get_json_converter()
        return {
            "date": self.date.isoformat() if self.date else None,
            "metrics": self.metrics.to_json_dict(),
            "top_holdings": [h.to_json_dict() for h in self.top_holdings],
            "allocation": c.unstructure(self.allocation),
        }

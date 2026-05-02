"""Module for report-related data models used in the CLI."""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Self

from niveshpy.core.converter import get_json_converter
from niveshpy.models.report import (
    Allocation,
    PerformanceHolding,
    PortfolioTotals,
    SummaryResult,
)


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
    top_holdings: Sequence[PerformanceHolding]
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
            top_holdings=summary.top_holdings,
            allocation=summary.allocation,
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the SummaryResultDisplay instance to a JSON-serializable dictionary."""
        c = get_json_converter()
        return {
            "date": self.date.isoformat() if self.date else None,
            "metrics": self.metrics.to_json_dict(),
            "top_holdings": c.unstructure(self.top_holdings),
            "allocation": c.unstructure(self.allocation),
        }

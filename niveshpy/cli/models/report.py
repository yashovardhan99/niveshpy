"""Module for report-related data models used in the CLI."""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from niveshpy.core.converter import get_json_converter
from niveshpy.models.report import (
    Allocation,
    PerformanceHolding,
    PortfolioTotals,
    SummaryResult,
)


@dataclass(slots=True, frozen=True)
class SummaryResultDisplay:
    """Portfolio summary combining metrics, top holdings, and allocation."""

    date: datetime.date | None
    metrics: PortfolioTotals
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
            metrics=summary.metrics,
            top_holdings=summary.top_holdings,
            allocation=summary.allocation,
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the SummaryResultDisplay instance to a JSON-serializable dictionary."""
        c = get_json_converter()
        return {
            "date": self.date.isoformat() if self.date else None,
            "metrics": c.unstructure(self.metrics),
            "top_holdings": c.unstructure(self.top_holdings),
            "allocation": c.unstructure(self.allocation),
        }

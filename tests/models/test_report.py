"""Tests for all report models."""

import datetime
from decimal import Decimal

from niveshpy.models.account import AccountPublic
from niveshpy.models.report import (
    Allocation,
    Holding,
    PerformanceHolding,
    PerformanceResult,
    PortfolioTotals,
    SummaryResult,
)
from niveshpy.models.security import (
    SecurityCategory,
    SecurityPublic,
    SecurityType,
)

# --- Performance models ---


class TestPerformanceHoldingModel:
    """Tests for PerformanceHolding model."""

    def _make_holding(
        self,
        amount=Decimal("1100"),
        invested=Decimal("1000"),
        date=datetime.date(2024, 6, 1),
    ):
        account = AccountPublic(
            id=1,
            name="Savings",
            institution="Bank",
            created_at=datetime.datetime.now(),
            properties={},
        )
        security = SecurityPublic(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.datetime.now(),
        )
        return Holding(
            account=account,
            security=security,
            date=date,
            units=Decimal("100"),
            amount=amount,
            invested=invested,
        )

    def test_from_holding_computes_gains(self):
        """Test from_holding computes gains correctly."""
        holding = self._make_holding(amount=Decimal("1100"), invested=Decimal("1000"))
        perf = PerformanceHolding.from_holding(holding, xirr=Decimal("0.12"))
        assert perf.current_value == Decimal("1100")
        assert perf.invested == Decimal("1000")
        assert perf.gains == Decimal("100.00")
        assert perf.gains_pct == Decimal("0.1000")
        assert perf.xirr == Decimal("0.12")

    def test_from_holding_propagates_account_and_security(self):
        """Test from_holding propagates account and security references."""
        holding = self._make_holding()
        perf = PerformanceHolding.from_holding(holding, xirr=None)
        assert perf.account.name == "Savings"
        assert perf.security.key == "MF001"

    def test_from_holding_propagates_date(self):
        """Test from_holding propagates date from holding."""
        holding = self._make_holding(date=datetime.date(2025, 3, 15))
        perf = PerformanceHolding.from_holding(holding, xirr=None)
        assert perf.date == datetime.date(2025, 3, 15)

    def test_from_holding_xirr_none(self):
        """Test from_holding accepts xirr=None."""
        holding = self._make_holding()
        perf = PerformanceHolding.from_holding(holding, xirr=None)
        assert perf.xirr is None

    def test_from_holding_invested_none(self):
        """Test from_holding with invested=None yields None gains."""
        holding = self._make_holding(invested=None)
        perf = PerformanceHolding.from_holding(holding, xirr=Decimal("0.05"))
        assert perf.invested is None
        assert perf.gains is None
        assert perf.gains_pct is None

    def test_from_holding_negative_gains(self):
        """Test from_holding with loss scenario."""
        holding = self._make_holding(amount=Decimal("900"), invested=Decimal("1000"))
        perf = PerformanceHolding.from_holding(holding, xirr=Decimal("-0.05"))
        assert perf.gains == Decimal("-100.00")
        assert perf.gains_pct == Decimal("-0.1000")


class TestPerformanceResultModel:
    """Tests for PerformanceResult model."""

    def test_create_with_holdings_and_totals(self):
        """Test creating PerformanceResult with holdings and totals."""
        account = AccountPublic(
            id=1,
            name="Savings",
            institution="Bank",
            created_at=datetime.datetime.now(),
            properties={},
        )
        security = SecurityPublic(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.datetime.now(),
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 6, 1),
            units=Decimal("100"),
            amount=Decimal("1100"),
            invested=Decimal("1000"),
        )
        perf_holding = PerformanceHolding.from_holding(holding, xirr=Decimal("0.12"))
        totals = PortfolioTotals(
            total_current_value=Decimal("1100"),
            total_invested=Decimal("1000"),
            total_gains=Decimal("100"),
            gains_percentage=Decimal("0.10"),
            xirr=Decimal("0.12"),
        )
        result = PerformanceResult(holdings=[perf_holding], totals=totals)
        assert len(result.holdings) == 1
        assert result.totals.total_current_value == Decimal("1100")

    def test_create_with_empty_holdings(self):
        """Test creating PerformanceResult with empty holdings list."""
        totals = PortfolioTotals(
            total_current_value=Decimal("0"),
            total_invested=None,
            total_gains=None,
            gains_percentage=None,
        )
        result = PerformanceResult(holdings=[], totals=totals)
        assert result.holdings == []
        assert result.totals.total_invested is None


class TestPortfolioTotalsLastUpdated:
    """Tests for PortfolioTotals.last_updated field."""

    def test_portfolio_totals_last_updated(self):
        """Test creating PortfolioTotals with last_updated set."""
        totals = PortfolioTotals(
            total_current_value=Decimal("5000"),
            total_invested=Decimal("4000"),
            total_gains=Decimal("1000"),
            gains_percentage=Decimal("0.25"),
            last_updated=datetime.date(2026, 3, 22),
        )
        assert totals.last_updated == datetime.date(2026, 3, 22)

    def test_portfolio_totals_last_updated_default_none(self):
        """Test PortfolioTotals defaults last_updated to None."""
        totals = PortfolioTotals(
            total_current_value=Decimal("5000"),
            total_invested=None,
            total_gains=None,
            gains_percentage=None,
        )
        assert totals.last_updated is None


class TestSummaryResultModel:
    """Tests for SummaryResult model."""

    def test_summary_result_creation(self):
        """Test creating SummaryResult with all fields populated."""
        account = AccountPublic(
            id=1,
            name="Savings",
            institution="Bank",
            created_at=datetime.datetime.now(),
            properties={},
        )
        security = SecurityPublic(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.datetime.now(),
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 6, 1),
            units=Decimal("100"),
            amount=Decimal("1100"),
            invested=Decimal("1000"),
        )
        perf_holding = PerformanceHolding.from_holding(holding, xirr=Decimal("0.12"))
        totals = PortfolioTotals(
            total_current_value=Decimal("1100"),
            total_invested=Decimal("1000"),
            total_gains=Decimal("100"),
            gains_percentage=Decimal("0.10"),
            xirr=Decimal("0.12"),
        )
        alloc = Allocation(
            date=datetime.date(2024, 6, 1),
            amount=Decimal("1100"),
            allocation=Decimal("1.0"),
            security_category=SecurityCategory.EQUITY,
            security_type=None,
        )
        result = SummaryResult(
            as_of=datetime.date(2024, 6, 1),
            metrics=totals,
            top_holdings=[perf_holding],
            allocation=[alloc],
        )
        assert result.as_of == datetime.date(2024, 6, 1)
        assert result.metrics.total_current_value == Decimal("1100")
        assert len(result.top_holdings) == 1
        assert len(result.allocation) == 1

    def test_summary_result_empty_holdings(self):
        """Test creating SummaryResult with empty lists and as_of=None."""
        totals = PortfolioTotals(
            total_current_value=Decimal("0"),
            total_invested=None,
            total_gains=None,
            gains_percentage=None,
        )
        result = SummaryResult(
            as_of=None,
            metrics=totals,
            top_holdings=[],
            allocation=[],
        )
        assert result.as_of is None
        assert result.top_holdings == []
        assert result.allocation == []

    def test_summary_result_as_of_date(self):
        """Test as_of field accepts a date and None."""
        totals = PortfolioTotals(
            total_current_value=Decimal("0"),
            total_invested=None,
            total_gains=None,
            gains_percentage=None,
        )
        with_date = SummaryResult(
            as_of=datetime.date(2025, 1, 1),
            metrics=totals,
            top_holdings=[],
            allocation=[],
        )
        assert with_date.as_of == datetime.date(2025, 1, 1)

        without_date = SummaryResult(
            as_of=None,
            metrics=totals,
            top_holdings=[],
            allocation=[],
        )
        assert without_date.as_of is None

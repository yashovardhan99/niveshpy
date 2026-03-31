"""Tests for all report models."""

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from niveshpy.exceptions import OperationError
from niveshpy.models.account import Account
from niveshpy.models.report import (
    Allocation,
    Holding,
    PerformanceHolding,
    PerformanceHoldingBase,
    PerformanceHoldingDisplay,
    PerformanceHoldingExport,
    PerformanceResult,
    PortfolioTotals,
    SummaryResult,
    _compute_holding_gains,
)
from niveshpy.models.security import Security, SecurityCategory, SecurityType

# --- Performance models ---


class TestComputeHoldingGains:
    """Tests for _compute_holding_gains helper."""

    def test_invested_none_returns_none_pair(self):
        """Test that invested=None returns (None, None)."""
        gains, gains_pct = _compute_holding_gains(Decimal("1100"), None)
        assert gains is None
        assert gains_pct is None

    def test_normal_positive_gains(self):
        """Test normal case with positive gains."""
        gains, gains_pct = _compute_holding_gains(Decimal("1100"), Decimal("1000"))
        assert gains == Decimal("100.00")
        assert gains_pct == Decimal("0.1000")

    def test_invested_zero_returns_gains_but_no_pct(self):
        """Test that invested=0 computes gains but gains_pct is None."""
        gains, gains_pct = _compute_holding_gains(Decimal("500"), Decimal("0"))
        assert gains == Decimal("500.00")
        assert gains_pct is None

    def test_negative_gains(self):
        """Test negative gains when amount < invested."""
        gains, gains_pct = _compute_holding_gains(Decimal("900"), Decimal("1000"))
        assert gains == Decimal("-100.00")
        assert gains_pct == Decimal("-0.1000")

    def test_zero_gains(self):
        """Test zero gains when amount equals invested."""
        gains, gains_pct = _compute_holding_gains(Decimal("1000"), Decimal("1000"))
        assert gains == Decimal("0.00")
        assert gains_pct == Decimal("0.0000")


class TestPerformanceHoldingBaseModel:
    """Tests for PerformanceHoldingBase model."""

    def test_create_with_all_fields(self):
        """Test creating PerformanceHoldingBase with all fields."""
        holding = PerformanceHoldingBase(
            date=datetime.date(2024, 6, 1),
            current_value=Decimal("1100.00"),
            invested=Decimal("1000.00"),
            gains=Decimal("100.00"),
            gains_pct=Decimal("0.1000"),
            xirr=Decimal("0.1200"),
        )
        assert holding.date == datetime.date(2024, 6, 1)
        assert holding.current_value == Decimal("1100.00")
        assert holding.invested == Decimal("1000.00")
        assert holding.gains == Decimal("100.00")
        assert holding.gains_pct == Decimal("0.1000")
        assert holding.xirr == Decimal("0.1200")

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        holding = PerformanceHoldingBase(
            date=datetime.date(2024, 6, 1),
            current_value=Decimal("1100.00"),
        )
        assert holding.invested is None
        assert holding.gains is None
        assert holding.gains_pct is None
        assert holding.xirr is None

    def test_date_can_be_none(self):
        """Test that date accepts None."""
        holding = PerformanceHoldingBase(
            date=None,
            current_value=Decimal("500.00"),
        )
        assert holding.date is None

    def test_missing_current_value_raises(self):
        """Test that missing current_value raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            PerformanceHoldingBase(date=datetime.date(2024, 1, 1))


class TestPerformanceHoldingModel:
    """Tests for PerformanceHolding model."""

    def _make_holding(
        self,
        amount=Decimal("1100"),
        invested=Decimal("1000"),
        date=datetime.date(2024, 6, 1),
    ):
        account = Account(id=1, name="Savings", institution="Bank")
        security = Security(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
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


class TestPerformanceHoldingDisplayModel:
    """Tests for PerformanceHoldingDisplay model."""

    def _make_perf_holding(
        self,
        account_name="Savings",
        institution="Bank",
        security_name="Equity Fund",
        security_key="MF001",
    ):
        account = Account(id=1, name=account_name, institution=institution)
        security = Security(
            key=security_key,
            name=security_name,
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 6, 1),
            units=Decimal("100"),
            amount=Decimal("1100"),
            invested=Decimal("1000"),
        )
        return PerformanceHolding.from_holding(holding, xirr=Decimal("0.12"))

    def test_from_holding_formats_account(self):
        """Test from_holding formats account as 'name (institution)'."""
        perf = self._make_perf_holding(account_name="My Fund", institution="HDFC")
        display = PerformanceHoldingDisplay.from_holding(perf)
        assert display.account == "My Fund (HDFC)"

    def test_from_holding_formats_security(self):
        """Test from_holding formats security as 'name (key)'."""
        perf = self._make_perf_holding(security_name="Large Cap", security_key="LC01")
        display = PerformanceHoldingDisplay.from_holding(perf)
        assert display.security == "Large Cap (LC01)"

    def test_from_holding_propagates_date(self):
        """Test from_holding propagates date."""
        perf = self._make_perf_holding()
        display = PerformanceHoldingDisplay.from_holding(perf)
        assert display.date == datetime.date(2024, 6, 1)

    def test_from_holding_propagates_numeric_fields(self):
        """Test from_holding propagates all numeric fields."""
        perf = self._make_perf_holding()
        display = PerformanceHoldingDisplay.from_holding(perf)
        assert display.current_value == perf.current_value
        assert display.invested == perf.invested
        assert display.gains == perf.gains
        assert display.gains_pct == perf.gains_pct
        assert display.xirr == perf.xirr


class TestPerformanceHoldingExportModel:
    """Tests for PerformanceHoldingExport model."""

    def _make_perf_holding(self, account_id=1):
        account = Account(id=account_id, name="Savings", institution="Bank")
        security = Security(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 6, 1),
            units=Decimal("100"),
            amount=Decimal("1100"),
            invested=Decimal("1000"),
        )
        return PerformanceHolding.from_holding(holding, xirr=Decimal("0.12"))

    def test_from_holding_uses_account_id(self):
        """Test from_holding uses account.id (int)."""
        perf = self._make_perf_holding(account_id=42)
        export = PerformanceHoldingExport.from_holding(perf)
        assert export.account == 42

    def test_from_holding_uses_security_key(self):
        """Test from_holding uses security.key (str)."""
        perf = self._make_perf_holding()
        export = PerformanceHoldingExport.from_holding(perf)
        assert export.security == "MF001"

    def test_from_holding_propagates_date(self):
        """Test from_holding propagates date."""
        perf = self._make_perf_holding()
        export = PerformanceHoldingExport.from_holding(perf)
        assert export.date == datetime.date(2024, 6, 1)

    def test_from_holding_raises_when_account_id_none(self):
        """Test from_holding raises OperationError when account.id is None."""
        account = Account(name="NoID", institution="Bank")
        security = Security(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 6, 1),
            units=Decimal("100"),
            amount=Decimal("1100"),
            invested=Decimal("1000"),
        )
        perf = PerformanceHolding.from_holding(holding, xirr=None)
        with pytest.raises(OperationError, match="Account ID is required"):
            PerformanceHoldingExport.from_holding(perf)

    def test_from_holding_propagates_numeric_fields(self):
        """Test from_holding propagates all numeric fields."""
        perf = self._make_perf_holding()
        export = PerformanceHoldingExport.from_holding(perf)
        assert export.current_value == perf.current_value
        assert export.invested == perf.invested
        assert export.gains == perf.gains
        assert export.gains_pct == perf.gains_pct
        assert export.xirr == perf.xirr


class TestPerformanceResultModel:
    """Tests for PerformanceResult model."""

    def test_create_with_holdings_and_totals(self):
        """Test creating PerformanceResult with holdings and totals."""
        account = Account(id=1, name="Savings", institution="Bank")
        security = Security(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
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
        account = Account(id=1, name="Savings", institution="Bank")
        security = Security(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
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

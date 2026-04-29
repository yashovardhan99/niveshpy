"""Tests for helpers module."""

import datetime
from decimal import Decimal

import pytest

from niveshpy.exceptions import OperationError
from niveshpy.models.transaction import TransactionPublic, TransactionType
from niveshpy.services.helpers import compute_cagr, compute_xirr


def _make_txn(
    *,
    id: int,
    txn_type: TransactionType,
    units: Decimal,
    amount: Decimal,
    security_key: str = "SEC1",
    account_id: int = 1,
    date: datetime.date = datetime.date(2024, 1, 1),
    description: str = "",
) -> TransactionPublic:
    """Create a TransactionPublic object for testing."""
    return TransactionPublic(
        id=id,
        transaction_date=date,
        type=txn_type,
        description=description or f"{txn_type.value} {units} units",
        amount=amount,
        units=units,
        security_key=security_key,
        account_id=account_id,
        properties={},
        created=datetime.datetime.now(),
    )


def _buy(
    id: int,
    units: str,
    amount: str,
    *,
    security_key: str = "SEC1",
    account_id: int = 1,
    date: datetime.date = datetime.date(2024, 1, 1),
) -> TransactionPublic:
    return _make_txn(
        id=id,
        txn_type=TransactionType.PURCHASE,
        units=Decimal(units),
        amount=Decimal(amount),
        security_key=security_key,
        account_id=account_id,
        date=date,
    )


def _sell(
    id: int,
    units: str,
    amount: str,
    *,
    security_key: str = "SEC1",
    account_id: int = 1,
    date: datetime.date = datetime.date(2024, 1, 1),
) -> TransactionPublic:
    """Create a sell transaction. Units and amount provided as positive; will be negated."""
    return _make_txn(
        id=id,
        txn_type=TransactionType.SALE,
        units=-Decimal(units),
        amount=-Decimal(amount),
        security_key=security_key,
        account_id=account_id,
        date=date,
    )


class TestComputeCagr:
    """Tests for compute_cagr function."""

    def test_basic_growth(self):
        """10000 invested growing to 15000 over 2 years yields ~22.47% CAGR."""
        result = compute_cagr(
            invested=Decimal("10000"),
            current_value=Decimal("15000"),
            start_date=datetime.date(2022, 1, 1),
            end_date=datetime.date(2024, 1, 1),
        )
        assert abs(result - Decimal("0.2247")) < Decimal("0.01")

    def test_total_loss(self):
        """10000 invested dropping to 0 returns CAGR of -1.0000."""
        result = compute_cagr(
            invested=Decimal("10000"),
            current_value=Decimal("0"),
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2024, 1, 1),
        )
        assert result == Decimal("-1.0000")

    def test_no_growth(self):
        """10000 invested remaining at 10000 after 1 year returns 0.0000."""
        result = compute_cagr(
            invested=Decimal("10000"),
            current_value=Decimal("10000"),
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2024, 1, 1),
        )
        assert result == Decimal("0.0000")

    def test_short_period(self):
        """Short 30-day period produces a valid high annualized rate."""
        result = compute_cagr(
            invested=Decimal("10000"),
            current_value=Decimal("10100"),
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 31),
        )
        # 1% in 30 days → high annualized rate, should be positive
        assert result > Decimal("0.10")

    def test_negative_invested_raises(self):
        """Invested amount <= 0 should raise OperationError."""
        with pytest.raises(OperationError, match="Invested amount must be positive"):
            compute_cagr(
                invested=Decimal("-1000"),
                current_value=Decimal("15000"),
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2024, 1, 1),
            )

    def test_zero_invested_raises(self):
        """Invested amount of zero should raise OperationError."""
        with pytest.raises(OperationError, match="Invested amount must be positive"):
            compute_cagr(
                invested=Decimal("0"),
                current_value=Decimal("15000"),
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2024, 1, 1),
            )

    def test_negative_current_value_raises(self):
        """Negative current_value should raise OperationError."""
        with pytest.raises(OperationError, match="Current value cannot be negative"):
            compute_cagr(
                invested=Decimal("10000"),
                current_value=Decimal("-5000"),
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2024, 1, 1),
            )

    def test_invalid_date_range_raises(self):
        """End date <= start date should raise OperationError."""
        with pytest.raises(OperationError, match="End date must be after start date"):
            compute_cagr(
                invested=Decimal("10000"),
                current_value=Decimal("15000"),
                start_date=datetime.date(2024, 1, 1),
                end_date=datetime.date(2023, 1, 1),
            )

    def test_same_date_raises(self):
        """Same start and end date should raise OperationError."""
        with pytest.raises(OperationError, match="End date must be after start date"):
            compute_cagr(
                invested=Decimal("10000"),
                current_value=Decimal("15000"),
                start_date=datetime.date(2024, 1, 1),
                end_date=datetime.date(2024, 1, 1),
            )

    def test_explicit_end_date(self):
        """Passing an explicit end_date returns correct CAGR for that period."""
        result = compute_cagr(
            invested=Decimal("10000"),
            current_value=Decimal("12000"),
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 7, 1),
        )
        # ~20% growth in ~6 months → high annualized CAGR
        assert result > Decimal("0.30")

    def test_extreme_growth_short_period_raises(self):
        """Extreme growth over a very short period raises OperationError."""
        with pytest.raises(OperationError, match="numerical result out of range"):
            compute_cagr(
                invested=Decimal("10000"),
                current_value=Decimal("1000000"),
                start_date=datetime.date(2024, 1, 1),
                end_date=datetime.date(2024, 1, 2),
            )

    def test_default_end_date(self):
        """Omitting end_date defaults to today and produces a valid CAGR."""
        result = compute_cagr(
            invested=Decimal("10000"),
            current_value=Decimal("12000"),
            start_date=datetime.date(2020, 1, 1),
        )
        assert result > Decimal("0.0")


class TestComputeXirr:
    """Tests for compute_xirr function."""

    def test_simple_purchase_and_growth(self):
        """Single purchase of 10000 with current value 12000 after ~1 year."""
        txns = [_buy(1, "100", "10000", date=datetime.date(2023, 1, 1))]
        result = compute_xirr(
            txns,
            current_value=Decimal("12000"),
            current_date=datetime.date(2024, 1, 1),
        )
        # ~20% annual return
        assert abs(result - Decimal("0.20")) < Decimal("0.05")

    def test_purchase_and_sale_with_remaining(self):
        """Buy 10000, sell 5000 later, remaining value 6000 yields valid XIRR."""
        txns = [
            _buy(1, "100", "10000", date=datetime.date(2023, 1, 1)),
            _sell(2, "50", "5500", date=datetime.date(2023, 7, 1)),
        ]
        result = compute_xirr(
            txns,
            current_value=Decimal("6000"),
            current_date=datetime.date(2024, 1, 1),
        )
        # Net positive return
        assert result > Decimal("0.0")

    def test_multiple_purchases(self):
        """Two purchases of 5000 each with current value 12000 yields valid XIRR."""
        txns = [
            _buy(1, "50", "5000", date=datetime.date(2023, 1, 1)),
            _buy(2, "50", "5000", date=datetime.date(2023, 7, 1)),
        ]
        result = compute_xirr(
            txns,
            current_value=Decimal("12000"),
            current_date=datetime.date(2024, 1, 1),
        )
        assert result > Decimal("0.10")

    def test_total_loss(self):
        """Buy 10000, current value 0 raises OperationError (boundary case)."""
        txns = [_buy(1, "100", "10000", date=datetime.date(2023, 1, 1))]
        with pytest.raises(OperationError, match="Could not compute XIRR"):
            compute_xirr(
                txns,
                current_value=Decimal("0"),
                current_date=datetime.date(2024, 1, 1),
            )

    def test_empty_transactions_raises(self):
        """Empty transaction list should raise OperationError."""
        with pytest.raises(OperationError, match="No transactions provided"):
            compute_xirr([], current_value=Decimal("10000"))

    def test_multi_security(self):
        """Transactions across 2 securities with combined current value."""
        txns = [
            _buy(
                1, "100", "10000", security_key="SEC1", date=datetime.date(2023, 1, 1)
            ),
            _buy(2, "50", "5000", security_key="SEC2", date=datetime.date(2023, 1, 1)),
        ]
        result = compute_xirr(
            txns,
            current_value=Decimal("18000"),
            current_date=datetime.date(2024, 1, 1),
        )
        # 15000 invested, 18000 current → positive XIRR
        assert result > Decimal("0.10")

    def test_explicit_current_date(self):
        """Passing explicit current_date yields correct XIRR."""
        txns = [_buy(1, "100", "10000", date=datetime.date(2023, 1, 1))]
        result = compute_xirr(
            txns,
            current_value=Decimal("11000"),
            current_date=datetime.date(2023, 7, 1),
        )
        # ~10% in ~6 months → high annualized rate
        assert result > Decimal("0.15")

    def test_known_xirr_value(self):
        """Well-known XIRR example with approximate expected value.

        Buy 10000 on 2023-01-01, buy 5000 on 2023-07-01, current value
        16500 on 2024-01-01. The XIRR should be approximately 13-15%.
        """
        txns = [
            _buy(1, "100", "10000", date=datetime.date(2023, 1, 1)),
            _buy(2, "50", "5000", date=datetime.date(2023, 7, 1)),
        ]
        result = compute_xirr(
            txns,
            current_value=Decimal("16500"),
            current_date=datetime.date(2024, 1, 1),
        )
        # Approximate check within tolerance
        assert abs(result - Decimal("0.14")) < Decimal("0.05"), (
            f"Expected XIRR ~0.14, got {result}"
        )

    def test_default_current_date(self):
        """Omitting current_date defaults to today and produces a valid XIRR."""
        txns = [_buy(1, "100", "10000", date=datetime.date(2020, 1, 1))]
        result = compute_xirr(txns, current_value=Decimal("15000"))
        assert result > Decimal("0.0")

    def test_all_zero_cash_flows_raises(self):
        """All-zero cash flows should raise OperationError."""
        txns = [_buy(1, "100", "0", date=datetime.date(2023, 1, 1))]
        with pytest.raises(OperationError, match="All cash flows are zero"):
            compute_xirr(
                txns,
                current_value=Decimal("0"),
                current_date=datetime.date(2024, 1, 1),
            )

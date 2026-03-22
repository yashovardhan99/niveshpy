"""Tests for helpers module."""

import datetime
from decimal import Decimal

import pytest

from niveshpy.exceptions import OperationError
from niveshpy.models.transaction import (
    Transaction,
    TransactionPublicWithCost,
    TransactionType,
)
from niveshpy.services.helpers import (
    compute_cagr,
    compute_cost_basis,
    compute_invested_amount,
    compute_xirr,
)


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
) -> Transaction:
    """Create a Transaction object for testing."""
    return Transaction(
        id=id,
        transaction_date=date,
        type=txn_type,
        description=description or f"{txn_type.value} {units} units",
        amount=amount,
        units=units,
        security_key=security_key,
        account_id=account_id,
    )


def _buy(
    id: int,
    units: str,
    amount: str,
    *,
    security_key: str = "SEC1",
    account_id: int = 1,
    date: datetime.date = datetime.date(2024, 1, 1),
) -> Transaction:
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
) -> Transaction:
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


class TestComputeCostBasisPurchasesOnly:
    """Tests for purchase-only transaction lists."""

    def test_single_purchase_has_no_cost(self):
        """Single purchase transaction should have cost=None."""
        txns = [_buy(1, "100", "10000")]
        result = compute_cost_basis(txns)
        assert len(result) == 1
        assert result[0].cost is None

    def test_multiple_purchases_all_have_no_cost(self):
        """All purchase transactions should have cost=None."""
        txns = [
            _buy(1, "100", "10000"),
            _buy(2, "50", "6000"),
            _buy(3, "200", "25000"),
        ]
        result = compute_cost_basis(txns)
        assert len(result) == 3
        assert all(r.cost is None for r in result)

    def test_empty_list(self):
        """Empty transaction list should return empty result."""
        result = compute_cost_basis([])
        assert result == []


class TestComputeCostBasisBasicFIFO:
    """Tests for basic FIFO cost basis calculations."""

    def test_buy_then_sell_all(self):
        """Sell all units from a single purchase — cost equals purchase amount."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
        ]
        result = compute_cost_basis(txns)
        assert len(result) == 2
        assert result[0].cost is None
        assert result[1].cost == Decimal("10000.00")

    def test_buy_then_partial_sell(self):
        """Sell half the units — cost is proportional."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "50", "6000"),
        ]
        result = compute_cost_basis(txns)
        assert result[1].cost == Decimal("5000.00")

    def test_sell_preserves_remaining_lot(self):
        """After a partial sell, a subsequent sell uses the remaining lot."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "40", "5000"),
            _sell(3, "60", "8000"),
        ]
        result = compute_cost_basis(txns)
        assert result[1].cost == Decimal("4000.00")
        assert result[2].cost == Decimal("6000.00")


class TestComputeCostBasisMultipleLots:
    """Tests for FIFO across multiple purchase lots."""

    def test_sell_spanning_two_lots(self):
        """Sell consumes the first lot entirely, then part of the second."""
        txns = [
            _buy(1, "50", "5000"),
            _buy(2, "100", "12000"),
            _sell(3, "80", "10000"),
        ]
        result = compute_cost_basis(txns)
        # First 50 units from lot 1: 5000
        # Next 30 units from lot 2: 12000 * (30/100) = 3600
        assert result[2].cost == Decimal("8600.00")

    def test_sell_consuming_multiple_lots_exactly(self):
        """Sell consumes two lots exactly."""
        txns = [
            _buy(1, "50", "5000"),
            _buy(2, "50", "6000"),
            _sell(3, "100", "15000"),
        ]
        result = compute_cost_basis(txns)
        assert result[2].cost == Decimal("11000.00")

    def test_multiple_sells_fifo_order(self):
        """Multiple sells consume lots in FIFO order."""
        txns = [
            _buy(1, "100", "10000", date=datetime.date(2024, 1, 1)),
            _buy(2, "100", "15000", date=datetime.date(2024, 2, 1)),
            _sell(3, "100", "13000", date=datetime.date(2024, 3, 1)),
            _sell(4, "100", "18000", date=datetime.date(2024, 4, 1)),
        ]
        result = compute_cost_basis(txns)
        # First sell uses first lot (100 @ 10000)
        assert result[2].cost == Decimal("10000.00")
        # Second sell uses second lot (100 @ 15000)
        assert result[3].cost == Decimal("15000.00")

    def test_three_lots_partial_sells(self):
        """Partial sells across three purchase lots."""
        txns = [
            _buy(1, "100", "10000"),
            _buy(2, "100", "12000"),
            _buy(3, "100", "15000"),
            _sell(4, "150", "20000"),
        ]
        result = compute_cost_basis(txns)
        # 100 from lot1: 10000
        # 50 from lot2: 12000 * (50/100) = 6000
        assert result[3].cost == Decimal("16000.00")


class TestComputeCostBasisMultipleSecurities:
    """Tests for independent tracking across securities."""

    def test_different_securities_tracked_independently(self):
        """Different securities should have independent cost-basis tracking."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _buy(2, "50", "8000", security_key="SEC2"),
            _sell(3, "100", "12000", security_key="SEC1"),
            _sell(4, "50", "9000", security_key="SEC2"),
        ]
        result = compute_cost_basis(txns)
        assert result[2].cost == Decimal("10000.00")
        assert result[3].cost == Decimal("8000.00")

    def test_sell_one_security_does_not_affect_other(self):
        """Selling one security should not consume lots of another."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _buy(2, "100", "15000", security_key="SEC2"),
            _sell(3, "50", "6000", security_key="SEC1"),
        ]
        result = compute_cost_basis(txns)
        assert len(result) == 3
        assert result[2].cost == Decimal("5000.00")


class TestComputeCostBasisMultipleAccounts:
    """Tests for independent tracking across accounts."""

    def test_different_accounts_tracked_independently(self):
        """Different accounts should have independent cost-basis tracking."""
        txns = [
            _buy(1, "100", "10000", account_id=1),
            _buy(2, "100", "15000", account_id=2),
            _sell(3, "100", "12000", account_id=1),
            _sell(4, "100", "18000", account_id=2),
        ]
        result = compute_cost_basis(txns)
        assert result[2].cost == Decimal("10000.00")
        assert result[3].cost == Decimal("15000.00")

    def test_same_security_different_accounts(self):
        """Same security key in different accounts should be tracked separately."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1", account_id=1),
            _buy(2, "100", "20000", security_key="SEC1", account_id=2),
            _sell(3, "50", "6000", security_key="SEC1", account_id=1),
            _sell(4, "50", "12000", security_key="SEC1", account_id=2),
        ]
        result = compute_cost_basis(txns)
        # account 1: cost per unit = 10000/100 = 100, so 50 units = 5000
        assert result[2].cost == Decimal("5000.00")
        # account 2: cost per unit = 20000/100 = 200, so 50 units = 10000
        assert result[3].cost == Decimal("10000.00")


class TestComputeCostBasisErrors:
    """Tests for error conditions."""

    def test_sell_without_prior_buy_raises(self):
        """Selling without any prior purchase should raise OperationError."""
        txns = [_sell(1, "100", "12000")]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            compute_cost_basis(txns)

    def test_sell_more_than_purchased_raises(self):
        """Selling more units than purchased should raise OperationError."""
        txns = [
            _buy(1, "50", "5000"),
            _sell(2, "100", "12000"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            compute_cost_basis(txns)

    def test_sell_for_different_security_with_no_buys_raises(self):
        """Selling a security with no purchase history should raise OperationError."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _sell(2, "50", "6000", security_key="SEC2"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            compute_cost_basis(txns)

    def test_sell_for_different_account_with_no_buys_raises(self):
        """Selling in an account with no purchase history should raise OperationError."""
        txns = [
            _buy(1, "100", "10000", account_id=1),
            _sell(2, "50", "6000", account_id=2),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            compute_cost_basis(txns)


class TestComputeCostBasisEdgeCases:
    """Tests for edge cases."""

    def test_same_day_buy_and_sell(self):
        """Buy and sell on the same day should compute cost correctly."""
        date = datetime.date(2024, 6, 15)
        txns = [
            _buy(1, "100", "10000", date=date),
            _sell(2, "100", "10500", date=date),
        ]
        result = compute_cost_basis(txns)
        assert result[1].cost == Decimal("10000.00")

    def test_very_small_units(self):
        """Very small fractional units should compute cost correctly."""
        txns = [
            _buy(1, "0.001", "10.50"),
            _sell(2, "0.001", "11.00"),
        ]
        result = compute_cost_basis(txns)
        assert result[1].cost == Decimal("10.50")

    def test_large_number_of_lots(self):
        """Many small buys followed by one large sell."""
        buys = [_buy(i, "10", str(1000 + i * 10)) for i in range(1, 21)]
        # Sell 200 units (all 20 lots)
        total_cost = sum(1000 + i * 10 for i in range(1, 21))
        sell = _sell(21, "200", "30000")
        txns = buys + [sell]
        result = compute_cost_basis(txns)
        assert result[-1].cost == Decimal(str(total_cost)).quantize(Decimal("0.01"))

    def test_interleaved_buy_sell_buy_sell(self):
        """Alternating buys and sells."""
        txns = [
            _buy(1, "100", "10000", date=datetime.date(2024, 1, 1)),
            _sell(2, "50", "6000", date=datetime.date(2024, 2, 1)),
            _buy(3, "100", "12000", date=datetime.date(2024, 3, 1)),
            _sell(4, "120", "16000", date=datetime.date(2024, 4, 1)),
        ]
        result = compute_cost_basis(txns)
        # First sell: 50 from lot1 (10000 * 50/100 = 5000)
        assert result[1].cost == Decimal("5000.00")
        # Second sell: 50 remaining from lot1 (5000) + 70 from lot2 (12000 * 70/100 = 8400) = 13400
        assert result[3].cost == Decimal("13400.00")

    def test_sell_after_all_lots_consumed_raises(self):
        """Selling after all lots are consumed should raise."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
            _sell(3, "50", "6000"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            compute_cost_basis(txns)


class TestComputeCostBasisOutputFormat:
    """Tests for output format and structure."""

    def test_returns_transaction_public_with_cost_instances(self):
        """All results should be TransactionPublicWithCost instances."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
        ]
        result = compute_cost_basis(txns)
        assert all(isinstance(r, TransactionPublicWithCost) for r in result)

    def test_preserves_transaction_fields(self):
        """Output should preserve all original transaction fields."""
        txn = _buy(
            1,
            "100.500",
            "10000.00",
            security_key="MYFUND",
            account_id=42,
            date=datetime.date(2024, 3, 15),
        )
        result = compute_cost_basis([txn])
        r = result[0]
        assert r.id == 1
        assert r.transaction_date == datetime.date(2024, 3, 15)
        assert r.type == TransactionType.PURCHASE
        assert r.amount == Decimal("10000.00")
        assert r.units == Decimal("100.500")
        assert r.security_key == "MYFUND"
        assert r.account_id == 42

    def test_cost_is_quantized_to_two_decimals(self):
        """Cost basis should be quantized to 2 decimal places."""
        txns = [
            _buy(1, "3", "10.00"),
            _sell(2, "1", "4.00"),
        ]
        result = compute_cost_basis(txns)
        cost = result[1].cost
        assert cost is not None
        # 10.00 / 3 * 1 = 3.333... → quantized to 3.33
        assert cost == Decimal("3.33")
        assert cost == cost.quantize(Decimal("0.01"))

    def test_output_length_matches_input(self):
        """Output list length should match input transaction count."""
        txns = [
            _buy(1, "100", "10000"),
            _buy(2, "50", "6000"),
            _sell(3, "30", "4000"),
        ]
        result = compute_cost_basis(txns)
        assert len(result) == len(txns)


class TestComputeInvestedAmountBasic:
    """Tests for basic compute_invested_amount functionality."""

    def test_empty_list(self):
        """Empty transaction list should return empty result."""
        result = compute_invested_amount([])
        assert result == {}

    def test_single_purchase(self):
        """Single purchase returns full amount as invested."""
        txns = [_buy(1, "100", "10000")]
        result = compute_invested_amount(txns)
        assert result[("SEC1", 1)] == Decimal("10000.00")

    def test_multiple_purchases_same_security(self):
        """Multiple purchases sum up to total invested."""
        txns = [
            _buy(1, "100", "10000"),
            _buy(2, "50", "6000"),
        ]
        result = compute_invested_amount(txns)
        assert result[("SEC1", 1)] == Decimal("16000.00")

    def test_buy_then_sell_all_returns_empty(self):
        """Selling all units means no remaining investment."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
        ]
        result = compute_invested_amount(txns)
        # Key should not be in result (0 remaining)
        assert ("SEC1", 1) not in result or result[("SEC1", 1)] == Decimal("0.00")

    def test_buy_then_partial_sell(self):
        """Partial sell reduces invested proportionally via FIFO."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "40", "5000"),
        ]
        result = compute_invested_amount(txns)
        # 60 remaining from 100-unit lot: 10000 * 60/100 = 6000
        assert result[("SEC1", 1)] == Decimal("6000.00")


class TestComputeInvestedAmountFIFO:
    """Tests for FIFO behavior in compute_invested_amount."""

    def test_sell_spanning_two_lots(self):
        """Sell consumes first lot entirely, then part of second."""
        txns = [
            _buy(1, "50", "5000"),
            _buy(2, "100", "12000"),
            _sell(3, "80", "10000"),
        ]
        result = compute_invested_amount(txns)
        # Remaining: 70 units from lot 2, cost = 12000 * 70/100 = 8400
        assert result[("SEC1", 1)] == Decimal("8400.00")

    def test_interleaved_buy_sell(self):
        """Alternating buys and sells track correctly."""
        txns = [
            _buy(1, "100", "10000", date=datetime.date(2024, 1, 1)),
            _sell(2, "50", "6000", date=datetime.date(2024, 2, 1)),
            _buy(3, "100", "12000", date=datetime.date(2024, 3, 1)),
            _sell(4, "20", "3000", date=datetime.date(2024, 4, 1)),
        ]
        result = compute_invested_amount(txns)
        # After sell 50: lot1 has 50 units @ 5000
        # After buy 100: lot1(50@5000), lot2(100@12000)
        # After sell 20: lot1 has 30 units @ 10000*30/100=3000
        # Remaining: lot1(30@3000) + lot2(100@12000) = 15000
        assert result[("SEC1", 1)] == Decimal("15000.00")


class TestComputeInvestedAmountMultipleKeys:
    """Tests for independent tracking across securities and accounts."""

    def test_different_securities(self):
        """Different securities tracked independently."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _buy(2, "50", "8000", security_key="SEC2"),
            _sell(3, "20", "2500", security_key="SEC1"),
        ]
        result = compute_invested_amount(txns)
        # SEC1: 80 remaining from 100-unit lot: 10000 * 80/100 = 8000
        assert result[("SEC1", 1)] == Decimal("8000.00")
        # SEC2: untouched
        assert result[("SEC2", 1)] == Decimal("8000.00")

    def test_same_security_different_accounts(self):
        """Same security in different accounts tracked independently."""
        txns = [
            _buy(1, "100", "10000", account_id=1),
            _buy(2, "100", "20000", account_id=2),
            _sell(3, "50", "6000", account_id=1),
        ]
        result = compute_invested_amount(txns)
        # Account 1: 50 remaining from 100-unit lot: 10000 * 50/100 = 5000
        assert result[("SEC1", 1)] == Decimal("5000.00")
        # Account 2: untouched
        assert result[("SEC1", 2)] == Decimal("20000.00")


class TestComputeInvestedAmountErrors:
    """Tests for error conditions."""

    def test_sell_without_buy_raises(self):
        """Selling without prior purchase should raise OperationError."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _sell(2, "50", "6000", security_key="SEC2"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            compute_invested_amount(txns)

    def test_oversell_raises(self):
        """Selling more than purchased should raise OperationError."""
        txns = [
            _buy(1, "50", "5000"),
            _sell(2, "100", "12000"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            compute_invested_amount(txns)


class TestComputeInvestedAmountOutput:
    """Tests for output format."""

    def test_invested_quantized_to_two_decimals(self):
        """Invested amounts should be quantized to 2 decimal places."""
        txns = [
            _buy(1, "3", "10.00"),
            _sell(2, "1", "4.00"),
        ]
        result = compute_invested_amount(txns)
        invested = result[("SEC1", 1)]
        # 10/3 * 2 = 6.666... → quantized to 6.67
        assert invested == Decimal("6.67")
        assert invested == invested.quantize(Decimal("0.01"))


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

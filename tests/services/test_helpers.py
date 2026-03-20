"""Tests for compute_cost_basis in helpers module."""

import datetime
from decimal import Decimal

import pytest

from niveshpy.exceptions import OperationError
from niveshpy.models.transaction import (
    Transaction,
    TransactionPublicWithCost,
    TransactionType,
)
from niveshpy.services.helpers import compute_cost_basis


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
    """Create a sell transaction. Units should be provided as positive; will be negated."""
    return _make_txn(
        id=id,
        txn_type=TransactionType.SALE,
        units=-Decimal(units),
        amount=Decimal(amount),
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

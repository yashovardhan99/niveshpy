"""Tests for LotAccountingService."""

import datetime
from decimal import Decimal

import pytest

from niveshpy.domain.services import LotAccountingService
from niveshpy.exceptions import InvalidInputError, OperationError
from niveshpy.models.transaction import TransactionPublic, TransactionType


@pytest.fixture(scope="function", autouse=True)
def lot_accounting_service():
    """Provide a fresh LotAccountingService for each test."""
    yield LotAccountingService()


def _buy(
    id: int,
    units: str,
    amount: str,
    *,
    security_key: str = "SEC1",
    account_id: int = 1,
    date: datetime.date = datetime.date(2024, 1, 1),
) -> TransactionPublic:
    return TransactionPublic(
        id=id,
        transaction_date=date,
        type=TransactionType.PURCHASE,
        description="Test Purchase",
        amount=Decimal(amount),
        units=Decimal(units),
        security_key=security_key,
        account_id=account_id,
        properties={},
        created=datetime.datetime.now(),
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
    return TransactionPublic(
        id=id,
        transaction_date=date,
        type=TransactionType.SALE,
        description="Test Sale",
        amount=-Decimal(amount),
        units=-Decimal(units),
        security_key=security_key,
        account_id=account_id,
        properties={},
        created=datetime.datetime.now(),
    )


class TestComputePositionCosts:
    """Unit tests for LotAccountingService.compute_position_costs."""

    def test_empty_list(self, lot_accounting_service: LotAccountingService):
        """Empty transaction list should return empty result."""
        result = lot_accounting_service.compute_position_costs([])
        assert result == {}

    def test_single_purchase(self, lot_accounting_service: LotAccountingService):
        """Single purchase returns full amount as invested."""
        txns = [_buy(1, "100", "10000")]
        result = lot_accounting_service.compute_position_costs(txns)
        assert result[("SEC1", 1)] == Decimal("10000.00")

    def test_multiple_purchases_same_security(
        self, lot_accounting_service: LotAccountingService
    ):
        """Multiple purchases sum up to total invested."""
        txns = [
            _buy(1, "100", "10000"),
            _buy(2, "50", "6000"),
        ]
        result = lot_accounting_service.compute_position_costs(txns)
        assert result[("SEC1", 1)] == Decimal("16000.00")

    def test_buy_then_sell_all_returns_empty(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling all units means no remaining investment."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
        ]
        result = lot_accounting_service.compute_position_costs(txns)
        # Key should not be in result (0 remaining)
        assert result[("SEC1", 1)] == Decimal("0.00")

    def test_buy_then_partial_sell(self, lot_accounting_service: LotAccountingService):
        """Partial sell reduces invested proportionally via FIFO."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "40", "5000"),
        ]
        result = lot_accounting_service.compute_position_costs(txns)
        # 60 remaining from 100-unit lot: 10000 * 60/100 = 6000
        assert result[("SEC1", 1)] == Decimal("6000.00")

    def test_sell_spanning_two_lots(self, lot_accounting_service: LotAccountingService):
        """Sell consumes first lot entirely, then part of second."""
        txns = [
            _buy(1, "50", "5000"),
            _buy(2, "100", "12000"),
            _sell(3, "80", "10000"),
        ]
        result = lot_accounting_service.compute_position_costs(txns)
        # Remaining: 70 units from lot 2, cost = 12000 * 70/100 = 8400
        assert result[("SEC1", 1)] == Decimal("8400.00")

    def test_interleaved_buy_sell(self, lot_accounting_service: LotAccountingService):
        """Alternating buys and sells track correctly."""
        txns = [
            _buy(1, "100", "10000", date=datetime.date(2024, 1, 1)),
            _sell(2, "50", "6000", date=datetime.date(2024, 2, 1)),
            _buy(3, "100", "12000", date=datetime.date(2024, 3, 1)),
            _sell(4, "20", "3000", date=datetime.date(2024, 4, 1)),
        ]
        result = lot_accounting_service.compute_position_costs(txns)
        # After sell 50: lot1 has 50 units @ 5000
        # After buy 100: lot1(50@5000), lot2(100@12000)
        # After sell 20: lot1 has 30 units @ 10000*30/100=3000
        # Remaining: lot1(30@3000) + lot2(100@12000) = 15000
        assert result[("SEC1", 1)] == Decimal("15000.00")

    def test_different_securities(self, lot_accounting_service: LotAccountingService):
        """Different securities tracked independently."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _buy(2, "50", "8000", security_key="SEC2"),
            _sell(3, "20", "2500", security_key="SEC1"),
        ]
        result = lot_accounting_service.compute_position_costs(txns)
        # SEC1: 80 remaining from 100-unit lot: 10000 * 80/100 = 8000
        assert result[("SEC1", 1)] == Decimal("8000.00")
        # SEC2: untouched
        assert result[("SEC2", 1)] == Decimal("8000.00")

    def test_same_security_different_accounts(
        self, lot_accounting_service: LotAccountingService
    ):
        """Same security in different accounts tracked independently."""
        txns = [
            _buy(1, "100", "10000", account_id=1),
            _buy(2, "100", "20000", account_id=2),
            _sell(3, "50", "6000", account_id=1),
        ]
        result = lot_accounting_service.compute_position_costs(txns)
        # Account 1: 50 remaining from 100-unit lot: 10000 * 50/100 = 5000
        assert result[("SEC1", 1)] == Decimal("5000.00")
        # Account 2: untouched
        assert result[("SEC1", 2)] == Decimal("20000.00")

    def test_sell_without_buy_raises(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling without prior purchase should raise OperationError."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _sell(2, "50", "6000", security_key="SEC2"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.compute_position_costs(txns)

    def test_oversell_raises(self, lot_accounting_service: LotAccountingService):
        """Selling more than purchased should raise OperationError."""
        txns = [
            _buy(1, "50", "5000"),
            _sell(2, "100", "12000"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.compute_position_costs(txns)

    def test_invested_quantized_to_two_decimals(
        self, lot_accounting_service: LotAccountingService
    ):
        """Invested amounts should be quantized to 2 decimal places."""
        txns = [
            _buy(1, "3", "10.00"),
            _sell(2, "1", "4.00"),
        ]
        result = lot_accounting_service.compute_position_costs(txns)
        invested = result[("SEC1", 1)]
        # 10/3 * 2 = 6.666... → quantized to 6.67
        assert invested == Decimal("6.67")
        assert invested == invested.quantize(Decimal("0.01"))


class TestAnnotateTransactionsWithCost:
    """Unit tests for LotAccountingService.annotate_transactions_with_cost."""

    def test_single_purchase_has_no_cost(
        self, lot_accounting_service: LotAccountingService
    ):
        """Single purchase transaction should have cost=None."""
        txns = [_buy(1, "100", "10000")]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert len(result) == 1
        assert result[0].cost is None

    def test_multiple_purchases_all_have_no_cost(
        self, lot_accounting_service: LotAccountingService
    ):
        """All purchase transactions should have cost=None."""
        txns = [
            _buy(1, "100", "10000"),
            _buy(2, "50", "6000"),
            _buy(3, "200", "25000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert len(result) == 3
        assert all(r.cost is None for r in result)

    def test_empty_list(self, lot_accounting_service: LotAccountingService):
        """Empty transaction list should return empty result."""
        result = lot_accounting_service.annotate_transactions_with_cost([])
        assert result == []

    def test_buy_then_sell_all(self, lot_accounting_service: LotAccountingService):
        """Sell all units from a single purchase — cost equals purchase amount."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert len(result) == 2
        assert result[0].cost is None
        assert result[1].cost == Decimal("10000.00")

    def test_buy_then_partial_sell(self, lot_accounting_service: LotAccountingService):
        """Sell half the units — cost is proportional."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "50", "6000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert result[1].cost == Decimal("5000.00")

    def test_sell_preserves_remaining_lot(
        self, lot_accounting_service: LotAccountingService
    ):
        """After a partial sell, a subsequent sell uses the remaining lot."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "40", "5000"),
            _sell(3, "60", "8000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert result[1].cost == Decimal("4000.00")
        assert result[2].cost == Decimal("6000.00")

    def test_sell_spanning_two_lots(self, lot_accounting_service: LotAccountingService):
        """Sell consumes the first lot entirely, then part of the second."""
        txns = [
            _buy(1, "50", "5000"),
            _buy(2, "100", "12000"),
            _sell(3, "80", "10000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        # First 50 units from lot 1: 5000
        # Next 30 units from lot 2: 12000 * (30/100) = 3600
        assert result[2].cost == Decimal("8600.00")

    def test_sell_consuming_multiple_lots_exactly(
        self, lot_accounting_service: LotAccountingService
    ):
        """Sell consumes two lots exactly."""
        txns = [
            _buy(1, "50", "5000"),
            _buy(2, "50", "6000"),
            _sell(3, "100", "15000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert result[2].cost == Decimal("11000.00")

    def test_multiple_sells_fifo_order(
        self, lot_accounting_service: LotAccountingService
    ):
        """Multiple sells consume lots in FIFO order."""
        txns = [
            _buy(1, "100", "10000", date=datetime.date(2024, 1, 1)),
            _buy(2, "100", "15000", date=datetime.date(2024, 2, 1)),
            _sell(3, "100", "13000", date=datetime.date(2024, 3, 1)),
            _sell(4, "100", "18000", date=datetime.date(2024, 4, 1)),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        # First sell uses first lot (100 @ 10000)
        assert result[2].cost == Decimal("10000.00")
        # Second sell uses second lot (100 @ 15000)
        assert result[3].cost == Decimal("15000.00")

    def test_three_lots_partial_sells(
        self, lot_accounting_service: LotAccountingService
    ):
        """Partial sells across three purchase lots."""
        txns = [
            _buy(1, "100", "10000"),
            _buy(2, "100", "12000"),
            _buy(3, "100", "15000"),
            _sell(4, "150", "20000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        # 100 from lot1: 10000
        # 50 from lot2: 12000 * (50/100) = 6000
        assert result[3].cost == Decimal("16000.00")

    def test_different_securities_tracked_independently(
        self, lot_accounting_service: LotAccountingService
    ):
        """Different securities should have independent cost-basis tracking."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _buy(2, "50", "8000", security_key="SEC2"),
            _sell(3, "100", "12000", security_key="SEC1"),
            _sell(4, "50", "9000", security_key="SEC2"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert result[2].cost == Decimal("10000.00")
        assert result[3].cost == Decimal("8000.00")

    def test_sell_one_security_does_not_affect_other(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling one security should not consume lots of another."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _buy(2, "100", "15000", security_key="SEC2"),
            _sell(3, "50", "6000", security_key="SEC1"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert len(result) == 3
        assert result[2].cost == Decimal("5000.00")

    def test_different_accounts_tracked_independently(
        self, lot_accounting_service: LotAccountingService
    ):
        """Different accounts should have independent cost-basis tracking."""
        txns = [
            _buy(1, "100", "10000", account_id=1),
            _buy(2, "100", "15000", account_id=2),
            _sell(3, "100", "12000", account_id=1),
            _sell(4, "100", "18000", account_id=2),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert result[2].cost == Decimal("10000.00")
        assert result[3].cost == Decimal("15000.00")

    def test_same_security_different_accounts(
        self, lot_accounting_service: LotAccountingService
    ):
        """Same security key in different accounts should be tracked separately."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1", account_id=1),
            _buy(2, "100", "20000", security_key="SEC1", account_id=2),
            _sell(3, "50", "6000", security_key="SEC1", account_id=1),
            _sell(4, "50", "12000", security_key="SEC1", account_id=2),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        # account 1: cost per unit = 10000/100 = 100, so 50 units = 5000
        assert result[2].cost == Decimal("5000.00")
        # account 2: cost per unit = 20000/100 = 200, so 50 units = 10000
        assert result[3].cost == Decimal("10000.00")

    def test_sell_without_prior_buy_raises(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling without any prior purchase should raise OperationError."""
        txns = [_sell(1, "100", "12000")]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.annotate_transactions_with_cost(txns)

    def test_sell_more_than_purchased_raises(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling more units than purchased should raise OperationError."""
        txns = [
            _buy(1, "50", "5000"),
            _sell(2, "100", "12000"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.annotate_transactions_with_cost(txns)

    def test_sell_for_different_security_with_no_buys_raises(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling a security with no purchase history should raise OperationError."""
        txns = [
            _buy(1, "100", "10000", security_key="SEC1"),
            _sell(2, "50", "6000", security_key="SEC2"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.annotate_transactions_with_cost(txns)

    def test_sell_for_different_account_with_no_buys_raises(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling in an account with no purchase history should raise OperationError."""
        txns = [
            _buy(1, "100", "10000", account_id=1),
            _sell(2, "50", "6000", account_id=2),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.annotate_transactions_with_cost(txns)

    def test_same_day_buy_and_sell(self, lot_accounting_service: LotAccountingService):
        """Buy and sell on the same day should compute cost correctly."""
        date = datetime.date(2024, 6, 15)
        txns = [
            _buy(1, "100", "10000", date=date),
            _sell(2, "100", "10500", date=date),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert result[1].cost == Decimal("10000.00")

    def test_very_small_units(self, lot_accounting_service: LotAccountingService):
        """Very small fractional units should compute cost correctly."""
        txns = [
            _buy(1, "0.001", "10.50"),
            _sell(2, "0.001", "11.00"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert result[1].cost == Decimal("10.50")

    def test_large_number_of_lots(self, lot_accounting_service: LotAccountingService):
        """Many small buys followed by one large sell."""
        buys = [_buy(i, "10", str(1000 + i * 10)) for i in range(1, 21)]
        # Sell 200 units (all 20 lots)
        total_cost = sum(1000 + i * 10 for i in range(1, 21))
        sell = _sell(21, "200", "30000")
        txns = buys + [sell]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert result[-1].cost == Decimal(str(total_cost)).quantize(Decimal("0.01"))

    def test_interleaved_buy_sell_buy_sell(
        self, lot_accounting_service: LotAccountingService
    ):
        """Alternating buys and sells."""
        txns = [
            _buy(1, "100", "10000", date=datetime.date(2024, 1, 1)),
            _sell(2, "50", "6000", date=datetime.date(2024, 2, 1)),
            _buy(3, "100", "12000", date=datetime.date(2024, 3, 1)),
            _sell(4, "120", "16000", date=datetime.date(2024, 4, 1)),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        # First sell: 50 from lot1 (10000 * 50/100 = 5000)
        assert result[1].cost == Decimal("5000.00")
        # Second sell: 50 remaining from lot1 (5000) + 70 from lot2 (12000 * 70/100 = 8400) = 13400
        assert result[3].cost == Decimal("13400.00")

    def test_sell_after_all_lots_consumed_raises(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling after all lots are consumed should raise."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
            _sell(3, "50", "6000"),
        ]
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.annotate_transactions_with_cost(txns)

    def test_returns_transaction_public_instances(
        self, lot_accounting_service: LotAccountingService
    ):
        """All results should be TransactionPublic instances."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert all(isinstance(r, TransactionPublic) for r in result)

    def test_preserves_transaction_fields(
        self, lot_accounting_service: LotAccountingService
    ):
        """Output should preserve all original transaction fields."""
        txn = _buy(
            1,
            "100.500",
            "10000.00",
            security_key="MYFUND",
            account_id=42,
            date=datetime.date(2024, 3, 15),
        )
        result = lot_accounting_service.annotate_transactions_with_cost([txn])
        r = result[0]
        assert r.id == 1
        assert r.transaction_date == datetime.date(2024, 3, 15)
        assert r.type == TransactionType.PURCHASE
        assert r.amount == Decimal("10000.00")
        assert r.units == Decimal("100.500")
        assert r.security_key == "MYFUND"
        assert r.account_id == 42

    def test_cost_is_quantized_to_two_decimals(
        self, lot_accounting_service: LotAccountingService
    ):
        """Cost basis should be quantized to 2 decimal places."""
        txns = [
            _buy(1, "3", "10.00"),
            _sell(2, "1", "4.00"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        cost = result[1].cost
        assert cost is not None
        # 10.00 / 3 * 1 = 3.333... → quantized to 3.33
        assert cost == Decimal("3.33")
        assert cost == cost.quantize(Decimal("0.01"))

    def test_output_length_matches_input(
        self, lot_accounting_service: LotAccountingService
    ):
        """Output list length should match input transaction count."""
        txns = [
            _buy(1, "100", "10000"),
            _buy(2, "50", "6000"),
            _sell(3, "30", "4000"),
        ]
        result = lot_accounting_service.annotate_transactions_with_cost(txns)
        assert len(result) == len(txns)


class TestComputeRealizedLotEvents:
    """Unit tests for LotAccountingService.compute_realized_lot_events."""

    def test_one_sale_across_two_lots(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling across two lots should produce correct realized events."""
        txns = [
            _buy(1, "50", "5000", date=datetime.date(2024, 1, 1)),
            _buy(2, "100", "12000", date=datetime.date(2024, 2, 1)),
            _sell(3, "80", "10000", date=datetime.date(2024, 3, 1)),
        ]
        events = lot_accounting_service.compute_realized_lot_events(txns)
        assert len(events) == 2
        # First event: 50 units from lot 1 at cost 5000
        assert events[0].matched_units == Decimal("50")
        assert events[0].matched_cost == Decimal("5000.00")
        assert events[0].account_id == 1
        assert events[0].security_key == "SEC1"
        assert events[0].disposal_transaction_id == 3
        assert events[0].matched_open_transaction_id == 1
        assert events[0].proceeds_allocated == (
            Decimal(10_000) / Decimal(80) * Decimal(50)
        )  # Proceeds allocated proportionally
        assert (
            events[0].gain_loss == events[0].proceeds_allocated - events[0].matched_cost
        )
        assert (
            events[0].holding_days
            == (datetime.date(2024, 3, 1) - datetime.date(2024, 1, 1)).days
        )

        # Second event: 30 units from lot 2 at cost 12000 * (30/100) = 3600
        assert events[1].matched_units == Decimal("30")
        assert events[1].matched_cost == Decimal("3600.00")
        assert events[1].account_id == 1
        assert events[1].security_key == "SEC1"
        assert events[1].disposal_transaction_id == 3
        assert events[1].matched_open_transaction_id == 2
        assert events[1].proceeds_allocated == (
            Decimal(10_000) / Decimal(80) * Decimal(30)
        )  # Proceeds allocated proportionally
        assert (
            events[1].gain_loss == events[1].proceeds_allocated - events[1].matched_cost
        )
        assert (
            events[1].holding_days
            == (datetime.date(2024, 3, 1) - datetime.date(2024, 2, 1)).days
        )

    def test_sell_without_prior_buy_raises(
        self, lot_accounting_service: LotAccountingService
    ):
        """Selling without any prior purchase should raise OperationError."""
        txns = [_sell(1, "100", "12000")]

        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.compute_realized_lot_events(txns)

    def test_oversell_raises(self, lot_accounting_service: LotAccountingService):
        """Selling more units than purchased should raise OperationError."""
        txns = [
            _buy(1, "50", "5000"),
            _sell(2, "100", "12000"),
        ]

        with pytest.raises(OperationError, match="Insufficient purchase history"):
            lot_accounting_service.compute_realized_lot_events(txns)


class TestBuildOpenLotState:
    """Unit tests for LotAccountingService.build_open_lot_state."""

    def test_empty_list(self, lot_accounting_service: LotAccountingService):
        """Empty transaction list should return empty open lot state."""
        result = lot_accounting_service.build_open_lot_state([])
        assert result == {}

    def test_buy_then_sell_all_results_in_empty_state(
        self, lot_accounting_service: LotAccountingService
    ):
        """Buying and then selling all units should result in empty open lot state."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "100", "12000"),
        ]
        result = lot_accounting_service.build_open_lot_state(txns)
        assert ("SEC1", 1) in result
        assert len(result[("SEC1", 1)]) == 0

    def test_buy_then_partial_sell_results_in_remaining_lot(
        self, lot_accounting_service: LotAccountingService
    ):
        """Partial sell should leave remaining lot in open lot state."""
        txns = [
            _buy(1, "100", "10000"),
            _sell(2, "40", "5000"),
        ]
        result = lot_accounting_service.build_open_lot_state(txns)
        assert len(result) == 1
        assert result[("SEC1", 1)][0].remaining_units == Decimal("60")
        assert result[("SEC1", 1)][0].remaining_cost == Decimal("6000.00")

    def test_invalid_order_of_transactions_raises(
        self, lot_accounting_service: LotAccountingService
    ):
        """Transactions that are out of order or invalid should raise OperationError."""
        txns = [
            _buy(2, "100", "10000", date=datetime.date(2024, 2, 1)),
            _sell(1, "50", "6000", date=datetime.date(2024, 1, 1)),
        ]

        with pytest.raises(
            InvalidInputError, match="Transactions must be in chronological order"
        ):
            lot_accounting_service.build_open_lot_state(txns)

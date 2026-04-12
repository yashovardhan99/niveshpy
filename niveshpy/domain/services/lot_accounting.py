"""Domain service for lot accounting using FIFO matching."""

import datetime
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from niveshpy.domain.models.lot import OpenLot, RealizedLotEvent
from niveshpy.exceptions import InvalidInputError, OperationError
from niveshpy.models.transaction import (
    Transaction,
    TransactionPublicWithCost,
    TransactionType,
)


@dataclass(slots=True, frozen=True)
class LotAccountingService:
    """Pure domain service for FIFO lot accounting.

    Has no infrastructure dependencies. Callers are responsible for fetching
    the transaction stream (sorted by transaction_date ASC, id ASC) via their
    repository before passing it here.
    """

    def _run_fifo(
        self,
        transactions: Sequence[Transaction],
    ) -> tuple[Mapping[tuple[str, int], Sequence[OpenLot]], Sequence[RealizedLotEvent]]:
        """Core FIFO engine. Single pass over the transaction stream.

        Produces open lots (remaining holdings) and realized lot events
        (disposal match records) simultaneously. The stream must be sorted
        chronologically (transaction_date ASC, id ASC) by the caller —
        the engine does not sort.

        Args:
            transactions: Persisted transactions in chronological order.

        Returns:
            Tuple of (open_lots, realized_events).

        Raises:
            OperationError: If a sale cannot be fully covered by existing lots.
        """
        open_lots: defaultdict[tuple[str, int], list[OpenLot]] = defaultdict(list)
        realized_events: list[RealizedLotEvent] = []

        # Track the last transaction date per (security_key, account_id) to enforce chronological order
        last_transaction_date: dict[tuple[str, int], datetime.date] = {}

        for txn in transactions:
            if txn.id is None:
                raise InvalidInputError(
                    txn, "All transactions must have non-None ids for cost annotation."
                )

            key: tuple[str, int] = (txn.security_key, txn.account_id)

            # Validate chronological order per position key
            if (
                key in last_transaction_date
                and txn.transaction_date < last_transaction_date[key]
            ):
                raise InvalidInputError(
                    txn,
                    f"Transactions must be in chronological order per (security_key, account_id). "
                    f"Previous transaction date: {last_transaction_date[key]}, current transaction date: {txn.transaction_date}",
                )

            last_transaction_date[key] = txn.transaction_date

            # Only PURCHASE and SALE types are relevant for lot accounting; skip others.
            if txn.type == TransactionType.PURCHASE:
                # Purchases create new open lots
                open_lots[key].append(OpenLot.from_transaction(txn))

            elif txn.type == TransactionType.SALE:
                # Sales consume open lots

                if not open_lots[key]:
                    raise OperationError(
                        "Insufficient purchase history for cost basis calculation."
                    )

                units_to_sell = -txn.units  # sale units are stored negative
                total_units_sold = units_to_sell

                while units_to_sell > Decimal("0") and open_lots[key]:
                    lot = open_lots[key][0]
                    cost_per_unit = lot.remaining_cost / lot.remaining_units
                    matched_units = min(lot.remaining_units, units_to_sell)
                    matched_cost = cost_per_unit * matched_units
                    units_to_sell -= matched_units
                    updated_lot = lot.consume(matched_units)
                    if updated_lot is None:
                        # Entire lot consumed, remove it
                        open_lots[key].pop(0)
                    else:
                        # Lot partially consumed, update it
                        open_lots[key][0] = updated_lot

                    # Allocate proceeds proportionally to the matched units
                    proceeds_allocated = (matched_units / total_units_sold) * txn.amount

                    realized_events.append(
                        RealizedLotEvent(
                            disposal_transaction_id=txn.id,
                            matched_open_transaction_id=lot.source_transaction_id,
                            security_key=txn.security_key,
                            account_id=txn.account_id,
                            matched_units=matched_units,
                            matched_cost=matched_cost.quantize(Decimal("0.0001")),
                            proceeds_allocated=proceeds_allocated.quantize(
                                Decimal("0.0001")
                            ),
                            holding_days=(
                                txn.transaction_date - lot.acquisition_date
                            ).days,
                        )
                    )

                if units_to_sell > Decimal("0"):
                    raise OperationError(
                        "Insufficient purchase history for cost basis calculation."
                    )

        return dict(open_lots), realized_events

    def build_open_lot_state(
        self,
        transactions: Sequence[Transaction],
    ) -> Mapping[tuple[str, int], Sequence[OpenLot]]:
        """Return remaining open lots per (security_key, account_id).

        Args:
            transactions: Persisted transactions in chronological order.

        Returns:
            Mapping of position key to list of unconsumed OpenLot objects,
            in FIFO order (oldest first).
        """
        open_lots, _ = self._run_fifo(transactions)
        return open_lots

    def compute_position_costs(
        self,
        transactions: Sequence[Transaction],
    ) -> Mapping[tuple[str, int], Decimal]:
        """Return remaining cost basis per (security_key, account_id).

        Replaces compute_invested_amount in services/helpers.py.

        Args:
            transactions: Persisted transactions in chronological order.

        Returns:
            Mapping of position key to total remaining cost, quantized to 0.01.
        """
        open_lots = self.build_open_lot_state(transactions)
        return {
            key: sum((lot.remaining_cost for lot in lots), Decimal("0")).quantize(
                Decimal("0.01")
            )
            for key, lots in open_lots.items()
        }

    def annotate_transactions_with_cost(
        self,
        transactions: Sequence[Transaction],
    ) -> Sequence[TransactionPublicWithCost]:
        """Return transactions annotated with FIFO cost basis for each sale.

        Purchases receive cost=None. Sales receive the total matched cost
        consumed from open lots, quantized to 0.01.

        Replaces compute_cost_basis in services/helpers.py.

        Args:
            transactions: Persisted transactions in chronological order.

        Returns:
            Sequence of TransactionPublicWithCost in the original input order.
        """
        _, realized_events = self._run_fifo(transactions)

        # Sum matched_cost per disposal transaction
        cost_by_disposal: dict[int, Decimal] = defaultdict(Decimal)
        for event in realized_events:
            cost_by_disposal[event.disposal_transaction_id] += event.matched_cost

        result: list[TransactionPublicWithCost] = []
        for txn in transactions:
            if txn.id is None:
                raise InvalidInputError(
                    txn, "All transactions must have non-None ids for cost annotation."
                )

            if txn.type == TransactionType.PURCHASE:
                cost = None
            else:
                cost = cost_by_disposal[txn.id].quantize(Decimal("0.01"))
            result.append(
                TransactionPublicWithCost.model_validate(
                    {**txn.model_dump(), "cost": cost}
                )
            )
        return result

    def compute_realized_lot_events(
        self,
        transactions: Sequence[Transaction],
    ) -> Sequence[RealizedLotEvent]:
        """Return all realized lot events produced by the FIFO engine.

        One sale transaction produces one RealizedLotEvent per purchase lot
        consumed. These are the extension seam for future tax computation.

        Args:
            transactions: Persisted transactions in chronological order.

        Returns:
            Sequence of RealizedLotEvent in disposal order.
        """
        _, realized_events = self._run_fifo(transactions)
        return realized_events

"""Domain model for a lot in niveshpy."""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class OpenLot:
    """A single purchase lot that has not been fully consumed by sales.

    Produced by the FIFO engine as it walks the chronological transaction
    stream. What remains after all sales have been consumed represents the
    current cost basis of a held position.

    Attributes:
        security_key: Identifies which security this lot belongs to.
        account_id: Identifies which account/folio this lot belongs to.
            Combined with security_key this gives the (position) partition key.
        source_transaction_id: The Transaction.id of the purchase that
            opened this lot.
        acquisition_date: The date the lot was opened. Used for computing
            holding period when tax classification is added later.
        remaining_units: Units from the original purchase still held after
            all FIFO consumption by subsequent sales. Always > 0 for an open lot.
        remaining_cost: Proportional cost corresponding to remaining_units.
            Derived from the original purchase amount as lots are partially consumed.
    """

    security_key: str
    account_id: int
    source_transaction_id: int
    acquisition_date: datetime.date
    remaining_units: Decimal
    remaining_cost: Decimal


@dataclass(slots=True, frozen=True)
class RealizedLotEvent:
    """A single lot-match record produced when a sale consumes part or all of an open lot.

    One sale transaction typically produces multiple RealizedLotEvents — one
    per purchase lot consumed in FIFO order. This is the extension seam for
    future tax computation: STCG/LTCG classification, grandfathering rules,
    and cost indexation all operate on these records.

    Attributes:
        disposal_transaction_id: The Transaction.id of the sale that triggered
            this match.
        matched_open_transaction_id: The Transaction.id of the purchase lot that
            was consumed.
        security_key: Security being disposed.
        account_id: Account/folio of the disposal.
        matched_units: Units consumed from the purchase lot in this match.
        matched_cost: Cost basis allocated to matched_units (proportional slice
            of the original purchase cost).
        proceeds_allocated: Proportional share of the sale proceeds allocated
            to this lot slice. For a full lot match this equals the full sale
            amount; for partial matches it is prorated by units.
        holding_days: Calendar days between acquisition_date and disposal date.
        gain_loss: proceeds_allocated - matched_cost. Positive = gain,
            negative = loss.
    """

    disposal_transaction_id: int
    matched_open_transaction_id: int
    security_key: str
    account_id: int
    matched_units: Decimal
    matched_cost: Decimal
    proceeds_allocated: Decimal
    holding_days: int
    gain_loss: Decimal = field(init=False)

    def __post_init__(self) -> None:
        """Compute gain/loss after initialization since it's derived from other fields."""
        object.__setattr__(
            self, "gain_loss", self.proceeds_allocated - self.matched_cost
        )

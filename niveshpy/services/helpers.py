"""Helpers for different services."""

from collections.abc import Sequence
from decimal import Decimal

from niveshpy.exceptions import OperationError
from niveshpy.models.transaction import (
    Transaction,
    TransactionPublicWithCost,
    TransactionType,
)


def compute_cost_basis(
    transactions: Sequence[Transaction],
) -> Sequence[TransactionPublicWithCost]:
    """Compute cost basis for a list of transactions.

    This function calculates the cost basis for each transaction in the provided list
    using the FIFO method.

    Args:
        transactions (Sequence[Transaction]): List of transactions.

    Returns:
        Sequence[TransactionPublicWithCost]: List of transactions with cost basis information.
    """
    buys: dict[tuple[str, int], list[tuple[Decimal, Decimal]]] = {}
    transactions_with_cost = []
    for txn in transactions:
        if txn.type == TransactionType.PURCHASE:
            key = (txn.security_key, txn.account_id)
            if key not in buys:
                buys[key] = []
            buys[key].append((txn.units, txn.amount))
            transactions_with_cost.append(
                TransactionPublicWithCost.model_validate(
                    {
                        **txn.model_dump(),
                        "cost": None,
                    }
                )
            )
        elif txn.type == TransactionType.SALE:
            key = (txn.security_key, txn.account_id)
            if key not in buys:
                raise OperationError(
                    "Insufficient purchase history for cost basis calculation."
                )

            units_to_sell = -txn.units
            cost_basis: Decimal = Decimal("0.00")
            while units_to_sell > Decimal("0.00") and buys[key]:
                purchase_units, purchase_amount = buys[key][0]
                if purchase_units <= units_to_sell:
                    cost_basis += purchase_amount
                    units_to_sell -= purchase_units
                    buys[key].pop(0)
                else:
                    cost_per_unit = purchase_amount / purchase_units
                    cost_basis += cost_per_unit * units_to_sell
                    buys[key][0] = (
                        purchase_units - units_to_sell,
                        purchase_amount - cost_per_unit * units_to_sell,
                    )
                    units_to_sell = Decimal("0.00")

            if units_to_sell > Decimal("0.00"):
                raise OperationError(
                    "Insufficient purchase history for cost basis calculation."
                )

            transactions_with_cost.append(
                TransactionPublicWithCost.model_validate(
                    {
                        **txn.model_dump(),
                        "cost": cost_basis.quantize(Decimal("0.01")),
                    }
                )
            )
    return transactions_with_cost

"""Helpers for different services."""

import datetime
import decimal
import math
from collections.abc import Sequence
from decimal import Decimal

from niveshpy.exceptions import OperationError
from niveshpy.models.transaction import TransactionPublic


def compute_cagr(
    invested: Decimal,
    current_value: Decimal,
    start_date: datetime.date,
    end_date: datetime.date | None = None,
) -> Decimal:
    """Compute the Compound Annual Growth Rate (CAGR).

    CAGR measures the annualized rate of return for an investment over a given
    time period, assuming profits are reinvested.

    Formula: (current_value / invested) ^ (365.25 / days_held) - 1

    Args:
        invested: The total amount invested. Must be positive.
        current_value: The current market value of the investment.
        start_date: The date the investment period began.
        end_date: The date the investment period ended. Defaults to today.

    Returns:
        Decimal: The CAGR as a decimal fraction quantized to 4 decimal places
            (e.g., Decimal("0.1234") represents 12.34%).

    Raises:
        OperationError: If invested amount is not positive, current value is
            negative, end date is not after start date, or the result
            overflows due to extreme inputs.
    """
    if invested <= Decimal("0"):
        raise OperationError("Invested amount must be positive for CAGR calculation")
    if current_value < Decimal("0"):
        raise OperationError("Current value cannot be negative for CAGR calculation")

    if end_date is None:
        end_date = datetime.date.today()

    days_held = (end_date - start_date).days
    if days_held <= 0:
        raise OperationError("End date must be after start date for CAGR calculation")

    if current_value == Decimal("0"):
        return Decimal("-1.0000")

    try:
        ratio = float(current_value) / float(invested)
        exponent = 365.25 / days_held
        cagr = ratio**exponent - 1
        return Decimal(str(cagr)).quantize(Decimal("0.0001"))
    except (OverflowError, decimal.InvalidOperation) as exc:
        raise OperationError(
            "Could not compute CAGR — numerical result out of range"
        ) from exc


def compute_xirr(
    transactions: Sequence[TransactionPublic],
    current_value: Decimal,
    current_date: datetime.date | None = None,
) -> Decimal:
    """Compute the Extended Internal Rate of Return (XIRR).

    XIRR finds the annualized discount rate that makes the net present value of
    a series of irregular cash flows equal to zero. Purchases are treated as
    negative cash flows (money out) and sales as positive (money in). A final
    positive cash flow representing the current portfolio value is appended on
    ``current_date``.

    Uses the formula: sum(cf_i / (1 + r)^((d_i - d_0) / 365.25)) = 0, solved
    via Newton's method (``scipy.optimize.newton``).

    Args:
        transactions: Transactions to include in the XIRR calculation.
        current_value: Current market value of the holdings.
        current_date: Valuation date for the final cash flow. Defaults to today.

    Returns:
        Decimal: The XIRR as a decimal fraction quantized to 4 decimal places
            (e.g., Decimal("0.1234") represents 12.34%).

    Raises:
        OperationError: If no transactions are provided, all cash flows are
            zero, or the solver fails to find a solution.
    """
    from scipy.optimize import newton

    if not transactions:
        raise OperationError("No transactions provided for XIRR calculation")

    if current_date is None:
        current_date = datetime.date.today()

    # Build cash flow list: (date, float_amount)
    # Purchases are stored as positive amounts (outflows), sales as negative
    # (inflows). Negating gives the correct XIRR sign convention.
    cash_flows: list[tuple[datetime.date, float]] = [
        (txn.transaction_date, -float(txn.amount)) for txn in transactions
    ]
    # Append terminal cash flow (current portfolio value)
    cash_flows.append((current_date, float(current_value)))

    # Sort by date so d_0 is the earliest
    cash_flows.sort(key=lambda cf: cf[0])

    # Check that not all cash flows are zero
    if all(cf == 0.0 for _, cf in cash_flows):
        raise OperationError("All cash flows are zero — cannot compute XIRR")

    d_0 = cash_flows[0][0]

    def _xnpv(rate: float) -> float:
        """Compute net present value for the given annual rate."""
        return sum(
            cf / (1.0 + rate) ** ((d - d_0).days / 365.25) for d, cf in cash_flows
        )

    try:
        rate = float(newton(_xnpv, x0=0.1, tol=1e-12, maxiter=1000))
    except (RuntimeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        raise OperationError("Could not compute XIRR — no solution found") from exc

    if not math.isfinite(rate):
        raise OperationError(
            "Could not compute XIRR — solver returned non-finite result"
        )

    return Decimal(str(rate)).quantize(Decimal("0.0001"))

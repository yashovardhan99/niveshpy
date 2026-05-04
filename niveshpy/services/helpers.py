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

    We use the pyxirr library for a robust implementation that handles edge cases
    better than a custom solver.

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
    from pyxirr import InvalidPaymentsError, xirr

    if not transactions:
        raise OperationError("No transactions provided for XIRR calculation")

    if current_date is None:
        current_date = datetime.date.today()

    cash_flows = [(txn.transaction_date, -txn.amount) for txn in transactions]
    cash_flows.append((current_date, current_value))

    try:
        rate = xirr(cash_flows)
    except InvalidPaymentsError as exc:
        raise OperationError("Could not compute XIRR — Invalid cash flows") from exc

    if rate is None:
        raise OperationError(
            "Could not compute XIRR — Failed to converge to a solution"
        )

    if math.isinf(rate):
        raise OperationError("Could not compute XIRR — Result is infinite")

    return Decimal(rate).quantize(Decimal("0.0001"))

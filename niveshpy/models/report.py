"""Reports related models."""

import datetime
import decimal
import functools
from collections.abc import Sequence

from attrs import field, frozen

from niveshpy.models._helper import quantize_decimal
from niveshpy.models.account import AccountPublic
from niveshpy.models.security import (
    SecurityCategory,
    SecurityPublic,
    SecurityType,
)

# Holdings

_quantize_units = functools.partial(quantize_decimal, places=3)
_quantize_amount = functools.partial(quantize_decimal, places=2)
_quantize_percentage = functools.partial(quantize_decimal, places=4)


def _optional_quantize_amount(
    value: decimal.Decimal | None,
) -> decimal.Decimal | None:
    """Quantize an amount value if it's not None."""
    return _quantize_amount(value) if value is not None else None


def _optional_quantize_percentage(
    value: decimal.Decimal | None,
) -> decimal.Decimal | None:
    """Quantize a percentage value if it's not None."""
    return _quantize_percentage(value) if value is not None else None


@frozen
class Holding:
    """Model representing a single holding used in report computations.

    Attributes:
        account: The account associated with the holding.
        security: The security associated with the holding.
        date: The date of the holding.
        units: The number of units held.
        invested: The total amount invested in the holding.
        amount: The current total value of the holding.
        account_id: The ID of the account associated with the holding.
        security_key: The key of the security associated with the holding.
    """

    account: AccountPublic
    security: SecurityPublic
    date: datetime.date
    units: decimal.Decimal = field(converter=_quantize_units)
    invested: decimal.Decimal = field(converter=_quantize_amount)
    amount: decimal.Decimal = field(converter=_quantize_amount)
    account_id: int = field(init=False)
    security_key: str = field(init=False)

    def __attrs_post_init__(self) -> None:
        """Set account_id and security_key after initialization."""
        object.__setattr__(self, "account_id", self.account.id)
        object.__setattr__(self, "security_key", self.security.key)


@frozen
class HoldingUnitRow:
    """Data class for a single row of holding units used in report computations."""

    security_key: str
    account_id: int
    total_units: decimal.Decimal = field(converter=_quantize_units)
    last_transaction_date: datetime.date


# Portfolio Totals


@frozen
class PortfolioTotals:
    """Portfolio-level aggregate totals."""

    total_current_value: decimal.Decimal = field(converter=_quantize_amount)
    total_invested: decimal.Decimal | None = field(converter=_optional_quantize_amount)
    total_gains: decimal.Decimal | None = field(converter=_optional_quantize_amount)
    gains_percentage: decimal.Decimal | None = field(
        converter=_optional_quantize_percentage
    )
    xirr: decimal.Decimal | None = field(
        converter=_optional_quantize_percentage, default=None
    )
    last_updated: datetime.date | None = None


# Allocations


@frozen
class Allocation:
    """Model representing allocation data for security type/category.

    Attributes:
        date: The date of the allocation.
        amount: The total amount allocated.
        allocation: The percentage allocation.
        security_type: The type of security (optional).
        security_category: The category of security (optional).
    """

    date: datetime.date
    amount: decimal.Decimal = field(converter=_quantize_amount)
    allocation: decimal.Decimal = field(converter=_quantize_percentage)
    security_type: SecurityType | None = None
    security_category: SecurityCategory | None = None

    def __post_init__(self) -> None:
        """Validate that at least one of security_type or security_category is provided."""
        if self.security_type is None and self.security_category is None:
            raise ValueError(
                "Either security_type or security_category must be provided."
            )


# Performance


@frozen
class PerformanceHolding:
    """Model representing per-holding performance data used in reports."""

    account: AccountPublic
    account_id: int = field(init=False)
    security: SecurityPublic
    security_key: str = field(init=False)
    date: datetime.date
    current_value: decimal.Decimal = field(converter=_quantize_amount)
    invested: decimal.Decimal | None = field(converter=_optional_quantize_amount)
    gains: decimal.Decimal | None = field(
        init=False, converter=_optional_quantize_amount
    )
    gains_pct: decimal.Decimal | None = field(
        init=False, converter=_optional_quantize_percentage
    )
    xirr: decimal.Decimal | None = field(converter=_optional_quantize_percentage)

    def __attrs_post_init__(self) -> None:
        """Set account ID, security key, and compute gains and gains percentage after initialization."""
        object.__setattr__(self, "account_id", self.account.id)
        object.__setattr__(self, "security_key", self.security.key)
        object.__setattr__(
            self,
            "gains",
            self.current_value - self.invested if self.invested is not None else None,
        )
        object.__setattr__(
            self,
            "gains_pct",
            _quantize_percentage(self.gains / self.invested)
            if self.gains is not None
            and self.invested is not None
            and self.invested != 0
            else None,
        )

    @classmethod
    def from_holding(
        cls, holding: Holding, xirr: decimal.Decimal | None
    ) -> "PerformanceHolding":
        """Create PerformanceHolding from Holding and XIRR value."""
        return cls(
            account=holding.account,
            security=holding.security,
            date=holding.date,
            current_value=holding.amount,
            invested=holding.invested,
            xirr=xirr,
        )


@frozen
class PerformanceResult:
    """Result of portfolio performance computation."""

    holdings: Sequence[PerformanceHolding]
    totals: PortfolioTotals


@frozen
class SummaryResult:
    """Portfolio summary combining metrics, top holdings, and allocation."""

    as_of: datetime.date | None
    metrics: PortfolioTotals
    top_holdings: Sequence[PerformanceHolding]
    allocation: Sequence[Allocation]

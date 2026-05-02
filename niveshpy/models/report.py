"""Reports related models."""

import datetime
import decimal
from collections.abc import Sequence
from dataclasses import dataclass, field

from attrs import field as attrs_field
from attrs import frozen

from niveshpy.models.account import AccountPublic
from niveshpy.models.security import (
    SecurityCategory,
    SecurityPublic,
    SecurityType,
)

# Holdings


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
    units: decimal.Decimal
    invested: decimal.Decimal
    amount: decimal.Decimal
    account_id: int = attrs_field(init=False)
    security_key: str = attrs_field(init=False)

    def __attrs_post_init__(self) -> None:
        """Set account_id and security_key after initialization."""
        object.__setattr__(self, "account_id", self.account.id)
        object.__setattr__(self, "security_key", self.security.key)


@dataclass(slots=True, frozen=True)
class HoldingUnitRow:
    """Data class for a single row of holding units used in report computations."""

    security_key: str
    account_id: int
    total_units: decimal.Decimal
    last_transaction_date: datetime.date


# Portfolio Totals


@dataclass(slots=True)
class PortfolioTotals:
    """Portfolio-level aggregate totals."""

    total_current_value: decimal.Decimal
    total_invested: decimal.Decimal | None
    total_gains: decimal.Decimal | None
    gains_percentage: decimal.Decimal | None
    xirr: decimal.Decimal | None = None
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
    amount: decimal.Decimal
    allocation: decimal.Decimal
    security_type: SecurityType | None = None
    security_category: SecurityCategory | None = None

    def __post_init__(self) -> None:
        """Validate that at least one of security_type or security_category is provided."""
        if self.security_type is None and self.security_category is None:
            raise ValueError(
                "Either security_type or security_category must be provided."
            )


# Performance


@dataclass(slots=True, frozen=True)
class PerformanceHolding:
    """Data class for per-holding performance data used in reports."""

    account: AccountPublic
    security: SecurityPublic
    date: datetime.date
    current_value: decimal.Decimal
    invested: decimal.Decimal | None
    gains: decimal.Decimal | None = field(init=False)
    gains_pct: decimal.Decimal | None = field(init=False)
    xirr: decimal.Decimal | None

    def __post_init__(self) -> None:
        """Compute gains and gains percentage after initialization."""
        object.__setattr__(
            self,
            "gains",
            self.current_value - self.invested if self.invested is not None else None,
        )
        object.__setattr__(
            self,
            "gains_pct",
            (self.gains / self.invested).quantize(decimal.Decimal("0.0001"))
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


@dataclass(slots=True, frozen=True)
class PerformanceResult:
    """Result of portfolio performance computation."""

    holdings: Sequence[PerformanceHolding]
    totals: PortfolioTotals


@dataclass(slots=True, frozen=True)
class SummaryResult:
    """Portfolio summary combining metrics, top holdings, and allocation."""

    as_of: datetime.date | None
    metrics: PortfolioTotals
    top_holdings: Sequence[PerformanceHolding]
    allocation: Sequence[Allocation]

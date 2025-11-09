"""Price data models."""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from niveshpy.cli.utils import output


@dataclass
class PriceDataRead:
    """Model for a single price data point."""

    security: str  # Formatted as "name (key)"
    """The security this price belongs to."""

    date: datetime.date
    """The date of this price."""

    open: Decimal
    """Opening price."""

    high: Decimal
    """Highest price."""

    low: Decimal
    """Lowest price."""

    close: Decimal
    """Closing price."""

    created: datetime.datetime
    """Timestamp when this price data was created."""

    metadata: dict[str, str]
    """Additional metadata associated with this price data."""

    @staticmethod
    def rich_format_map() -> "output.FormatMap":
        """Get a list of formatting styles for rich table display."""
        return [
            None,  # security
            "cyan",  # date
            None,  # open
            "green",  # high
            "red",  # low
            "bold",  # close
            "dim",  # created
            "dim",  # metadata
        ]


@dataclass
class PriceDataWrite:
    """Model for a single price data point."""

    security_key: str
    """The security key this price belongs to."""

    date: datetime.date
    """The date of this price."""

    open: Decimal
    """Opening price."""

    high: Decimal
    """Highest price."""

    low: Decimal
    """Lowest price."""

    close: Decimal
    """Closing price."""

    metadata: dict[str, str] = field(default_factory=dict)
    """Additional metadata associated with this price data."""

    @classmethod
    def from_single_price(
        cls,
        security_key: str,
        date: datetime.date,
        price: Decimal,
    ) -> "PriceDataWrite":
        """Create PriceData instance for a single price point.

        Args:
            security_key: The security key this price belongs to.
            date: The date of this price.
            price: The price value.

        Returns:
            An instance of PriceData with open, high, low, close set to the same price.
        """
        return cls(
            security_key=security_key,
            date=date,
            open=price,
            high=price,
            low=price,
            close=price,
        )

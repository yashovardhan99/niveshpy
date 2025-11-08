"""Price data models."""

import datetime
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PriceData:
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

    @classmethod
    def from_single_price(
        cls,
        security_key: str,
        date: datetime.date,
        price: Decimal,
    ) -> "PriceData":
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

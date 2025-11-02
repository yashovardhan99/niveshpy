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

    close: Decimal
    """Closing price (or single price point, if not OHLC)."""

    open: Decimal | None = None
    """Opening price (optional, for OHLC data)."""

    high: Decimal | None = None
    """Highest price (optional, for OHLC data)."""

    low: Decimal | None = None
    """Lowest price (optional, for OHLC data)."""

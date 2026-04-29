"""Price data models."""

import datetime
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from attrs import field, frozen

from niveshpy.models.security import SecurityPublic


@frozen
class PriceCreate:
    """Model for creating price data.

    Attributes:
        security_key (str): Foreign key to the associated security.
        date (datetime.date): Date of the price data.
        open (Decimal): Opening price.
        high (Decimal): Highest price.
        low (Decimal): Lowest price.
        close (Decimal): Closing price.
        properties (Mapping[str, Any]): Additional properties of the price data.
    """

    security_key: str
    date: datetime.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    properties: Mapping[str, Any] = field(factory=dict)


@frozen
class PricePublic:
    """Public model for price data exposure.

    Attributes:
        security_key (str): Foreign key to the associated security.
        date (datetime.date): Date of the price data.
        open (Decimal): Opening price.
        high (Decimal): Highest price.
        low (Decimal): Lowest price.
        close (Decimal): Closing price.
        properties (dict[str, Any]): Additional properties of the price data.
        created (datetime.datetime): Timestamp when the price data was created.
        security (Security): Related security object, if set.
    """

    security_key: str
    date: datetime.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    properties: Mapping[str, Any]
    created: datetime.datetime
    security: SecurityPublic | None = field(default=None, repr=False)

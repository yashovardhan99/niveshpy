"""Price data models."""

import datetime
import functools
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from attrs import field, frozen

from niveshpy.models._helper import quantize_decimal
from niveshpy.models.security import SecurityPublic

_quantize_price = functools.partial(quantize_decimal, places=4)


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
    open: Decimal = field(converter=_quantize_price)
    high: Decimal = field(converter=_quantize_price)
    low: Decimal = field(converter=_quantize_price)
    close: Decimal = field(converter=_quantize_price)
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
        source (str | None): Source of the price data, extracted from properties if available.
    """

    security_key: str
    date: datetime.date
    open: Decimal = field(converter=_quantize_price)
    high: Decimal = field(converter=_quantize_price)
    low: Decimal = field(converter=_quantize_price)
    close: Decimal = field(converter=_quantize_price)
    properties: Mapping[str, Any]
    created: datetime.datetime
    security: SecurityPublic | None = field(default=None, repr=False)
    source: str | None = field(init=False)

    def __attrs_post_init__(self):
        """Set the source field based on properties after initialization."""
        object.__setattr__(self, "source", self.properties.get("source"))

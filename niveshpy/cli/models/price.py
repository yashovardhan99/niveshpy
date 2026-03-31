"""Module for price-related data models used in the CLI."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar, Self

from niveshpy.cli.models.security import SecurityDisplay
from niveshpy.cli.utils.formatters import format_datetime, format_decimal
from niveshpy.cli.utils.models import Column

if TYPE_CHECKING:
    from niveshpy.models.price import PricePublicWithRelations


def _format_security(security: SecurityDisplay) -> str:
    return f"{security.name} ({security.key})"


@dataclass(slots=True, frozen=True)
class PriceDisplay:
    """Data class for displaying price information in CLI output."""

    security: SecurityDisplay
    date: datetime.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    created: datetime.datetime
    source: str | None
    columns: ClassVar[Sequence[Column]] = [
        Column("security", formatter=_format_security),
        Column("date", formatter=lambda d: d.strftime("%d %b %Y"), style="cyan"),
        Column("open", formatter=format_decimal, justify="right"),
        Column("high", formatter=format_decimal, style="green", justify="right"),
        Column("low", formatter=format_decimal, style="red", justify="right"),
        Column("close", formatter=format_decimal, style="bold", justify="right"),
        Column("created", style="dim", formatter=format_datetime),
        Column("source", style="dim"),
    ]
    csv_fields: ClassVar[Sequence[str]] = [
        "security",
        "date",
        "open",
        "high",
        "low",
        "close",
        "created",
        "source",
    ]

    @classmethod
    def from_domain(
        cls,
        price: PricePublicWithRelations,
    ) -> Self:
        """Create a PriceDisplay instance from a domain Price model."""
        return cls(
            security=SecurityDisplay.from_domain(price.security),
            date=price.date,
            open=price.open,
            high=price.high,
            low=price.low,
            close=price.close,
            created=price.created,
            source=price.properties.get("source"),
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the PriceDisplay instance to a JSON-serializable dictionary."""
        return {
            "security": self.security.to_json_dict(),
            "date": self.date.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "created": self.created.isoformat(),
            "source": self.source,
        }

    def to_csv_dict(self) -> dict[str, Any]:
        """Convert the PriceDisplay instance to a dictionary suitable for CSV output."""
        return {
            "security": self.security.key,
            "date": self.date.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "created": self.created.isoformat(),
            "source": self.source,
        }

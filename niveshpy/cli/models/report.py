"""Module for report-related data models used in the CLI."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from niveshpy.cli.models.account import AccountDisplay
from niveshpy.cli.models.security import SecurityDisplay
from niveshpy.cli.utils.formatters import format_date, format_decimal
from niveshpy.cli.utils.models import Column

if TYPE_CHECKING:
    from niveshpy.models.report import Holding


def _format_account(account: AccountDisplay) -> str:
    return f"{account.name} ({account.institution})"


def _format_security(security: SecurityDisplay) -> str:
    return f"{security.name} ({security.key})"


@dataclass(slots=True, frozen=True)
class HoldingDisplay:
    """Data class for displaying holding information in CLI output."""

    account: AccountDisplay
    security: SecurityDisplay
    date: datetime.date
    units: Decimal
    invested: Decimal | None
    current: Decimal

    columns: ClassVar[Sequence[Column]] = [
        Column("account", style="dim", formatter=_format_account),
        Column("security", style="bold", formatter=_format_security),
        Column("date", style="cyan", formatter=format_date),
        Column("units", style="dim", formatter=format_decimal, justify="right"),
        Column("invested", style="dim", formatter=format_decimal, justify="right"),
        Column("current", style="bold", formatter=format_decimal, justify="right"),
    ]
    csv_fields: ClassVar[Sequence[str]] = [
        "account",
        "security",
        "date",
        "units",
        "invested",
        "current",
    ]

    @classmethod
    def from_domain(cls, holding: Holding) -> "HoldingDisplay":
        """Create HoldingDisplay from Holding model."""
        return cls(
            account=AccountDisplay.from_domain(holding.account),
            security=SecurityDisplay.from_domain(holding.security),
            date=holding.date,
            units=holding.units,
            invested=holding.invested,
            current=holding.amount,
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the HoldingDisplay instance to a JSON-serializable dictionary."""
        return {
            "account": self.account.to_json_dict(),
            "security": self.security.to_json_dict(),
            "date": self.date.isoformat(),
            "units": str(self.units),
            "invested": str(self.invested) if self.invested is not None else None,
            "current": str(self.current),
        }

    def to_csv_dict(self) -> dict[str, Any]:
        """Convert the AccountDisplay instance to a dictionary suitable for CSV output."""
        return {
            "account": self.account.id,
            "security": self.security.key,
            "date": self.date.isoformat(),
            "units": self.units,
            "invested": self.invested,
            "current": self.current,
        }

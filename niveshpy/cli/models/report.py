"""Module for report-related data models used in the CLI."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from niveshpy.cli.models.account import AccountDisplay
from niveshpy.cli.models.security import (
    SecurityDisplay,
    _format_security_category,
    _format_security_type,
)
from niveshpy.cli.utils.formatters import format_date, format_decimal, format_percentage
from niveshpy.cli.utils.models import Column

if TYPE_CHECKING:
    from niveshpy.models.report import Allocation, Holding
    from niveshpy.models.security import SecurityCategory, SecurityType


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


@dataclass(slots=True, frozen=True)
class AllocationDisplay:
    """Data class for displaying allocation information in CLI output."""

    date: datetime.date
    amount: Decimal
    allocation: Decimal
    security_type: SecurityType | None
    security_category: SecurityCategory | None

    _base_columns: ClassVar[Sequence[Column]] = [
        Column("date", style="cyan", formatter=format_date),
        Column("amount", style="bold", formatter=format_decimal, justify="right"),
        Column(
            "allocation", style="bold", formatter=format_percentage, justify="right"
        ),
    ]
    _base_csv_fields: ClassVar[Sequence[str]] = ["date", "amount", "allocation"]

    def __post_init__(self) -> None:
        """Validate that at least one of security_type or security_category is provided."""
        if self.security_type is None and self.security_category is None:
            raise ValueError(
                "Either security_type or security_category must be provided."
            )

    @classmethod
    def from_domain(
        cls,
        allocation: Allocation,
    ) -> "AllocationDisplay":
        """Create an AllocationDisplay instance from a domain Allocation model."""
        return cls(
            date=allocation.date,
            amount=allocation.amount,
            allocation=allocation.allocation,
            security_type=allocation.security_type,
            security_category=allocation.security_category,
        )

    @classmethod
    def get_columns(
        cls, group_by: Literal["both", "type", "category"]
    ) -> Sequence[Column]:
        """Get the appropriate columns based on whether security type or category is used."""
        columns: list[Column] = []
        if group_by in ("both", "type"):
            columns.append(Column("security_type", formatter=_format_security_type))
        if group_by in ("both", "category"):
            columns.append(
                Column("security_category", formatter=_format_security_category)
            )
        columns.extend(cls._base_columns)
        return columns

    @classmethod
    def get_csv_fields(
        cls, group_by: Literal["both", "type", "category"]
    ) -> Sequence[str]:
        """Get the appropriate CSV fields based on whether security type or category is used."""
        fields: list[str] = []
        if group_by in ("both", "type"):
            fields.append("security_type")
        if group_by in ("both", "category"):
            fields.append("security_category")
        fields.extend(cls._base_csv_fields)
        return fields

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the AllocationDisplay instance to a JSON-serializable dictionary."""
        json_dict = {
            "date": self.date.isoformat(),
            "amount": str(self.amount),
            "allocation": str(self.allocation),
        }
        if self.security_type is not None:
            json_dict["security_type"] = self.security_type.value
        if self.security_category is not None:
            json_dict["security_category"] = self.security_category.value
        return json_dict

    def to_csv_dict(self) -> dict[str, Any]:
        """Convert the AllocationDisplay instance to a dictionary suitable for CSV output."""
        csv_dict = {
            "date": self.date.isoformat(),
            "amount": self.amount,
            "allocation": self.allocation,
        }
        if self.security_type is not None:
            csv_dict["security_type"] = self.security_type.value
        if self.security_category is not None:
            csv_dict["security_category"] = self.security_category.value
        return csv_dict

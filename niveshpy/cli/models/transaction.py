"""Module for transaction-related data models used in the CLI."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar, Self

from niveshpy.cli.models.account import AccountDisplay
from niveshpy.cli.models.security import SecurityDisplay
from niveshpy.cli.utils.formatters import format_date, format_datetime, format_decimal
from niveshpy.cli.utils.models import Column

if TYPE_CHECKING:
    from niveshpy.models.transaction import (
        TransactionPublicWithRelations,
        TransactionPublicWithRelationsAndCost,
        TransactionType,
    )


def _format_transaction_type(txn_type: TransactionType) -> str:
    from niveshpy.models.transaction import TransactionType

    type_format_map = {
        TransactionType.PURCHASE: "[green]Purchase",
        TransactionType.SALE: "[red]Sale",
    }
    return type_format_map.get(txn_type, "[reverse]Unknown")


def _format_account(account: AccountDisplay) -> str:
    return f"{account.name} ({account.institution})"


def _format_security(security: SecurityDisplay) -> str:
    return f"{security.name} ({security.key})"


@dataclass(slots=True, frozen=True)
class TransactionDisplay:
    """Data class for displaying transaction information in CLI output."""

    id: int
    transaction_date: datetime.date
    type: TransactionType
    description: str
    amount: Decimal
    units: Decimal
    security: SecurityDisplay
    account: AccountDisplay
    created: datetime.datetime
    source: str | None
    cost: Decimal | None = None
    columns: ClassVar[Sequence[Column]] = [
        Column("id", style="dim", justify="right"),
        Column(
            "transaction_date",
            name="Date",
            formatter=format_date,
            style="cyan",
        ),
        Column("type", formatter=_format_transaction_type),
        Column("description"),
        Column("security", formatter=_format_security),
        Column("amount", formatter=format_decimal, style="bold"),
        Column("units", formatter=format_decimal, style="cyan"),
        Column("account", formatter=_format_account, style="dim"),
        Column("created", style="dim", formatter=format_datetime),
        Column("source", style="dim"),
    ]
    columns_with_cost: ClassVar[Sequence[Column]] = (
        list(columns[:6])
        + [
            Column(
                "cost",
                formatter=lambda cost: format_decimal(cost) if cost is not None else "",
                style="bold magenta",
            ),
        ]
        + list(columns[6:])
    )
    csv_fields: ClassVar[Sequence[str]] = [
        "id",
        "transaction_date",
        "type",
        "description",
        "security",
        "amount",
        "units",
        "account",
        "created",
        "source",
    ]
    csv_fields_with_cost: ClassVar[Sequence[str]] = (
        list(csv_fields[:6]) + ["cost"] + list(csv_fields[6:])
    )

    @classmethod
    def from_domain(
        cls,
        transaction: TransactionPublicWithRelations
        | TransactionPublicWithRelationsAndCost,
    ) -> Self:
        """Create a TransactionDisplay instance from a domain Transaction model."""
        return cls(
            id=transaction.id,
            transaction_date=transaction.transaction_date,
            type=transaction.type,
            description=transaction.description,
            amount=transaction.amount,
            units=transaction.units,
            security=SecurityDisplay.from_domain(transaction.security),
            account=AccountDisplay.from_domain(transaction.account),
            created=transaction.created,
            source=transaction.properties.get("source"),
            cost=getattr(transaction, "cost", None),
        )

    def to_json_dict(self, include_cost: bool = False) -> dict[str, Any]:
        """Convert the TransactionDisplay instance to a JSON-serializable dictionary."""
        json_dict: dict[str, Any] = {
            "id": str(self.id),
            "transaction_date": self.transaction_date.isoformat(),
            "type": self.type.value,
            "description": self.description,
            "security": self.security.to_json_dict(),
            "amount": str(self.amount),
            "units": str(self.units),
            "account": self.account.to_json_dict(),
            "created": self.created.isoformat(),
            "source": self.source,
        }
        if include_cost:
            json_dict["cost"] = str(self.cost) if self.cost is not None else None
        return json_dict

    def to_csv_dict(self, include_cost: bool = False) -> dict[str, Any]:
        """Convert the TransactionDisplay instance to a dictionary suitable for CSV output."""
        csv_dict = {
            "id": self.id,
            "transaction_date": self.transaction_date.isoformat(),
            "type": self.type.value,
            "description": self.description,
            "security": self.security.key,
            "amount": self.amount,
            "units": self.units,
            "account": self.account.id,
            "created": self.created.isoformat(),
            "source": self.source,
        }
        if include_cost:
            csv_dict["cost"] = self.cost
        return csv_dict

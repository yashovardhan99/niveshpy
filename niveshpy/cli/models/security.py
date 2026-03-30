"""Module for account-related data models used in the CLI."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self

from niveshpy.cli.utils.output_models import Column
from niveshpy.models.output import format_datetime

if TYPE_CHECKING:
    from niveshpy.models.security import Security, SecurityCategory, SecurityType


def _format_security_type(sec_type: SecurityType) -> str:
    from niveshpy.models.security import SecurityType

    type_format_map = {
        SecurityType.STOCK.value: "[white]Stock",
        SecurityType.BOND.value: "[cyan]Bond",
        SecurityType.ETF.value: "[yellow]ETF",
        SecurityType.MUTUAL_FUND.value: "[green]Mutual Fund",
        SecurityType.OTHER.value: "[dim]Other",
    }
    return type_format_map.get(sec_type, "[reverse]Unknown")


def _format_security_category(category: SecurityCategory) -> str:
    from niveshpy.models.security import SecurityCategory

    category_format_map = {
        SecurityCategory.EQUITY.value: "[white]Equity",
        SecurityCategory.DEBT.value: "[cyan]Debt",
        SecurityCategory.COMMODITY.value: "[yellow]Commodity",
        SecurityCategory.REAL_ESTATE.value: "[bright_red]Real Estate",
        SecurityCategory.OTHER.value: "[dim]Other",
    }
    return category_format_map.get(category, "[reverse]Unknown")


@dataclass(slots=True, frozen=True)
class SecurityDisplay:
    """Data class for displaying security information in CLI output."""

    key: str
    name: str
    type: SecurityType
    category: SecurityCategory
    created: datetime.datetime
    source: str | None
    columns: ClassVar[Sequence[Column]] = [
        Column("key", style="green", justify="right"),
        Column("name"),
        Column("type", formatter=_format_security_type),
        Column("category", formatter=_format_security_category),
        Column("created", style="dim", formatter=format_datetime),
        Column("source", style="dim"),
    ]
    csv_fields: ClassVar[Sequence[str]] = [
        "key",
        "name",
        "type",
        "category",
        "created",
        "source",
    ]

    @classmethod
    def from_domain(cls, security: Security) -> Self:
        """Create a SecurityDisplay instance from a domain Security model."""
        return cls(
            key=security.key,
            name=security.name,
            type=security.type,
            category=security.category,
            created=security.created,
            source=security.properties.get("source"),
        )

    def to_json_dict(self) -> dict[str, str | None]:
        """Convert the SecurityDisplay instance to a JSON-serializable dictionary."""
        return {
            "key": self.key,
            "name": self.name,
            "type": self.type.value,
            "category": self.category.value,
            "created": self.created.isoformat(),
            "source": self.source,
        }

    def to_csv_dict(self) -> dict[str, str | None]:
        """Convert the SecurityDisplay instance to a dictionary suitable for CSV output."""
        return self.to_json_dict()

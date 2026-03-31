"""Module for account-related data models used in the CLI."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self

from niveshpy.cli.utils.formatters import format_datetime
from niveshpy.cli.utils.output_models import Column
from niveshpy.exceptions import ResourceError

if TYPE_CHECKING:
    from niveshpy.models.account import Account, AccountPublic


@dataclass(slots=True, frozen=True)
class AccountDisplay:
    """Data class for displaying account information in CLI output."""

    id: int
    name: str
    institution: str
    created: datetime.datetime
    source: str | None
    columns: ClassVar[Sequence[Column]] = [
        Column("id", name="ID", style="dim"),
        Column("name"),
        Column("institution", style="bold"),
        Column("created", style="dim", formatter=format_datetime),
        Column("source", style="dim"),
    ]
    csv_fields: ClassVar[Sequence[str]] = [
        "id",
        "name",
        "institution",
        "created",
        "source",
    ]

    @classmethod
    def from_domain(cls, account: AccountPublic | Account) -> Self:
        """Create an AccountDisplay instance from a domain Account model."""
        if account.id is None:
            msg = f"Invalid account data: missing ID for account '{account.name}'"
            raise ResourceError(msg)
        return cls(
            id=account.id,
            name=account.name,
            institution=account.institution,
            created=account.created_at,
            source=account.properties.get("source"),
        )

    def to_json_dict(self) -> dict[str, str | int | None]:
        """Convert the AccountDisplay instance to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "institution": self.institution,
            "created": self.created.isoformat(),
            "source": self.source,
        }

    def to_csv_dict(self) -> dict[str, str | int | None]:
        """Convert the AccountDisplay instance to a dictionary suitable for CSV output."""
        return self.to_json_dict()

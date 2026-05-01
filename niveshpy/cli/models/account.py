"""Module for account-related data models used in the CLI."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Self

from niveshpy.models.account import AccountPublic


@dataclass(slots=True, frozen=True)
class AccountDisplay:
    """Data class for displaying account information in CLI output."""

    id: int
    name: str
    institution: str
    created: datetime.datetime
    source: str | None

    @classmethod
    def from_domain(cls, account: AccountPublic) -> Self:
        """Create an AccountDisplay instance from a domain Account model."""
        return cls(
            id=account.id,
            name=account.name,
            institution=account.institution,
            created=account.created,
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

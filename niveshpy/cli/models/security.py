"""Module for security-related data models used in the CLI."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Self

from niveshpy.models.security import SecurityCategory, SecurityPublic, SecurityType


@dataclass(slots=True, frozen=True)
class SecurityDisplay:
    """Data class for displaying security information in CLI output."""

    key: str
    name: str
    type: SecurityType
    category: SecurityCategory
    created: datetime.datetime
    source: str | None

    @classmethod
    def from_domain(cls, security: SecurityPublic) -> Self:
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

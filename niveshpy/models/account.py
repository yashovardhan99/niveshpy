"""Account model for user financial data."""

from dataclasses import dataclass, field
from collections.abc import Callable
from datetime import datetime


@dataclass
class AccountRead:
    """Model for account data."""

    id: int
    name: str
    institution: str
    created_at: datetime
    metadata: dict[str, str]

    @staticmethod
    def rich_format_map() -> list[str | Callable[[str], str] | None]:
        """Get a list of formatting styles for rich table display."""
        return ["dim", "bold", None, "dim", "dim"]


@dataclass
class AccountWrite:
    """Model for creating or updating account data."""

    name: str
    institution: str
    metadata: dict[str, str] = field(default_factory=dict)

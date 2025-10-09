"""Account model for user financial data."""

from dataclasses import dataclass
from collections.abc import Callable


@dataclass
class AccountRead:
    """Model for account data."""

    id: int
    name: str
    institution: str

    @staticmethod
    def rich_format_map() -> list[str | Callable[[str], str] | None]:
        """Get a list of formatting styles for rich table display."""
        return ["dim", "bold", None]


@dataclass
class AccountWrite:
    """Model for creating or updating account data."""

    name: str
    institution: str

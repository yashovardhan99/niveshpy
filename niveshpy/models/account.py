"""Account model for user financial data."""

from dataclasses import dataclass


@dataclass
class AccountRead:
    """Model for account data."""

    id: int
    name: str
    institution: str


@dataclass
class AccountWrite:
    """Model for creating or updating account data."""

    name: str
    institution: str

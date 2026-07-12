"""Account model for user financial data."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from attrs import field, frozen


@frozen
class AccountCreate:
    """Model for creating a new account.

    Attributes:
        name (str): Name of the account.
        institution (str): Financial institution managing the account.
        properties (Mapping[str, Any], optional): Additional properties of the account.
            Defaults to an empty dictionary.
    """

    name: str
    institution: str
    properties: Mapping[str, Any] = field(factory=dict)


@frozen
class AccountPublic:
    """Public model for account data exposure.

    Attributes:
        id (int): Primary key ID of the account.
        name (str): Name of the account.
        institution (str): Financial institution managing the account.
        created (datetime): Timestamp when the account was created.
        properties (Mapping[str, Any]): Additional properties of the account.
        source (str | None): Optional source identifier extracted from properties.
    """

    id: int
    name: str
    institution: str
    created: datetime
    properties: Mapping[str, Any]
    source: str | None = field(default=None, init=False)

    def __attrs_post_init__(self) -> None:
        """Extract source from properties if available."""
        object.__setattr__(self, "source", self.properties.get("source"))

"""SQLite models for NiveshPy."""

from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel, UniqueConstraint

from niveshpy.models.security import SecurityCategory, SecurityType


class Account(SQLModel, table=True):
    """Database model for investment accounts.

    Attributes:
        id (int | None): Primary key ID of the account. None if not yet stored in DB.
        name (str): Name of the account.
        institution (str): Financial institution managing the account.
        properties (dict[str, Any]): Additional properties of the account.
        created_at (datetime): Timestamp when the account was created.
    """

    __table_args__ = (
        UniqueConstraint("name", "institution", name="uix_name_institution"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str
    institution: str
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)


class Security(SQLModel, table=True):
    """Database model for securities.

    Attributes:
        key (str): Unique key identifying the security.
        name (str): Name of the security.
        type (SecurityType): Type of the security.
        category (SecurityCategory): Category of the security.
        properties (dict[str, Any]): Additional properties of the security.
        created (datetime): Timestamp when the security was created.
    """

    key: str = Field(primary_key=True)
    name: str = Field()
    type: SecurityType = Field()
    category: SecurityCategory = Field()
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created: datetime = Field(default_factory=datetime.now)

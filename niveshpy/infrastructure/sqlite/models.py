"""SQLite models for NiveshPy."""

from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel, UniqueConstraint


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

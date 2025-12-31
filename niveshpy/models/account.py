"""Account model for user financial data."""

from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel, UniqueConstraint


class AccountBase(SQLModel):
    """Base model for investment accounts.

    Attributes:
        name (str): Name of the account.
        institution (str): Financial institution managing the account.
        properties (dict[str, Any], optional): Additional properties of the account.
            Defaults to an empty dictionary.
    """

    name: str = Field(schema_extra={"json_schema_extra": {"order": 1}})
    institution: str = Field(
        schema_extra={"json_schema_extra": {"style": "bold", "order": 2}}
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        schema_extra={"json_schema_extra": {"style": "dim", "order": 4}},
    )

    def __init_subclass__(cls, **kwargs):
        """Ensure subclasses inherit schema extra metadata."""
        return super().__init_subclass__(**kwargs)


class AccountCreate(AccountBase):
    """Model for creating a new account.

    Attributes:
        name (str): Name of the account.
        institution (str): Financial institution managing the account.
        properties (dict[str, Any], optional): Additional properties of the account.
            Defaults to an empty dictionary.
    """


class Account(AccountBase, table=True):
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
    created_at: datetime = Field(default_factory=datetime.now)


class AccountPublic(AccountBase):
    """Public model for account data exposure.

    Attributes:
        id (int): Primary key ID of the account.
        name (str): Name of the account.
        institution (str): Financial institution managing the account.
        created_at (datetime): Timestamp when the account was created.
        properties (dict[str, Any]): Additional properties of the account.
    """

    id: int = Field(
        title="ID",
        schema_extra={
            "json_schema_extra": {"style": "dim", "justify": "right", "order": 0}
        },
    )
    created_at: datetime = Field(
        title="Created",
        schema_extra={"json_schema_extra": {"style": "dim", "order": 3}},
    )

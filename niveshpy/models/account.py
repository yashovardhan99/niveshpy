"""Account model for user financial data."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlmodel import JSON, Column, Field, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from niveshpy.cli.utils import output


class AccountBase(SQLModel):
    """Base model for investment accounts."""

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
    """Model for creating a new account."""


class Account(AccountBase, table=True):
    """Database model for investment accounts."""

    __table_args__ = (
        UniqueConstraint("name", "institution", name="uix_name_institution"),
    )

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)


class AccountPublic(AccountBase):
    """Public model for account data exposure."""

    id: int = Field(
        title="ID",
        schema_extra={
            "json_schema_extra": {"style": "dim", "justify": "right", "order": 0}
        },
    )
    created_at: datetime = Field(
        title="Created",
        schema_extra={
            "json_schema_extra": {"style": "dim", "justify": "right", "order": 3}
        },
    )


@dataclass
class AccountRead:
    """Model for account data."""

    id: int
    name: str
    institution: str
    created_at: datetime
    metadata: dict[str, str]

    @staticmethod
    def rich_format_map() -> "output.FormatMap":
        """Get a list of formatting styles for rich table display."""
        return ["dim", "bold", None, "dim", "dim"]


@dataclass
class AccountWrite:
    """Model for creating or updating account data."""

    name: str
    institution: str
    metadata: dict[str, str] = field(default_factory=dict)

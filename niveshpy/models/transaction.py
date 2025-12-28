"""Models for financial transactions."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from pydantic import Field as PydanticField
from pydantic import field_validator
from sqlmodel import JSON, NUMERIC, Column, Field, Relationship, SQLModel

from niveshpy.core.query import ast
from niveshpy.models.account import Account
from niveshpy.models.security import Security

if TYPE_CHECKING:
    from niveshpy.cli.utils import output


class TransactionType(StrEnum):
    """Enum for transaction types."""

    PURCHASE = auto()
    SALE = auto()

    @staticmethod
    def rich_format(security_type: str) -> str:
        """Format the security type for display."""
        return type_format_map.get(security_type, "[reverse]Unknown")


type_format_map = {
    TransactionType.PURCHASE.value: "[green]Purchase",
    TransactionType.SALE.value: "[red]Sale",
}


class TransactionBase(SQLModel):
    """Base model for transactions."""

    transaction_date: date = Field(
        schema_extra={"json_schema_extra": {"order": 1, "style": "cyan"}}
    )
    type: TransactionType = Field(
        schema_extra={
            "json_schema_extra": {
                "order": 2,
                "formatter": lambda type: type_format_map.get(type, "[reverse]Unknown"),
            }
        }
    )
    description: str = Field(schema_extra={"json_schema_extra": {"order": 3}})
    amount: Decimal = Field(
        sa_column=Column(NUMERIC(24, 2)),
        schema_extra={
            "json_schema_extra": {"order": 4, "style": "bold", "justify": "right"}
        },
    )
    units: Decimal = Field(
        sa_column=Column(NUMERIC(24, 3)),
        schema_extra={
            "json_schema_extra": {"order": 5, "style": "yellow", "justify": "right"}
        },
    )
    security_key: str = Field(
        foreign_key="security.key",
        schema_extra={"json_schema_extra": {"hidden": True, "order": 6}},
    )
    account_id: int = Field(
        foreign_key="account.id",
        schema_extra={"json_schema_extra": {"hidden": True, "order": 7}},
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        schema_extra={"json_schema_extra": {"style": "dim", "order": 8}},
    )

    def __init_subclass__(cls, **kwargs):
        """Ensure subclasses are properly initialized."""
        return super().__init_subclass__(**kwargs)


class TransactionCreate(TransactionBase):
    """Model for creating transactions."""


class Transaction(TransactionBase, table=True):
    """Database model for transactions."""

    id: int | None = Field(default=None, primary_key=True)
    security: Security = Relationship()
    account: Account = Relationship()
    created: datetime = Field(default_factory=datetime.now)


class TransactionPublic(TransactionBase):
    """Public model for transactions."""

    id: int = Field(
        schema_extra={
            "json_schema_extra": {"style": "dim", "order": 0, "justify": "right"}
        },
    )
    created: datetime = Field(
        schema_extra={"json_schema_extra": {"style": "dim", "order": 9}},
    )


class TransactionDisplay(TransactionPublic):
    """Model for displaying transaction with related info."""

    security: str = PydanticField(
        json_schema_extra={"order": 6, "justify": "right"},
    )
    account: str = PydanticField(
        json_schema_extra={"order": 7, "justify": "right", "style": "dim"},
    )

    @field_validator("security", mode="before", json_schema_input_type=str | Security)
    @classmethod
    def validate_security(cls, value: str | Security) -> str:
        """Validate and format the security field."""
        if isinstance(value, Security):
            return f"{value.name} ({value.key})"
        return value

    @field_validator("account", mode="before", json_schema_input_type=str | Account)
    @classmethod
    def validate_account(cls, value: str | Account) -> str:
        """Validate and format the account field."""
        if isinstance(value, Account):
            return f"{value.name} ({value.institution})"
        return value


class TransactionPublicWithRelations(TransactionPublic):
    """Public model for transactions with related account and security info."""

    security: Security = Field(schema_extra={"json_schema_extra": {"order": 6}})
    account: Account = Field(schema_extra={"json_schema_extra": {"order": 7}})


@dataclass
class TransactionRead:
    """Model for reading transaction data."""

    id: int
    transaction_date: date
    type: TransactionType
    description: str
    amount: Decimal
    units: Decimal
    security: str  # Formatted as "name (key)"
    account: str  # Formatted as "name (institution)"
    created: datetime
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def rich_format_map() -> "output.FormatMap":
        """Get a list of formatting styles for rich table display."""
        return [
            "dim",  # id
            "cyan",  # date
            TransactionType.rich_format,  # type
            None,  # description
            "bold",  # amount
            "yellow",  # units
            None,  # security
            "dim",  # account
            "dim",  # created
            "dim",  # metadata
        ]


@dataclass
class TransactionWrite:
    """Model for transaction data."""

    transaction_date: date
    type: TransactionType
    description: str
    amount: Decimal
    units: Decimal
    security_key: str
    account_id: int
    metadata: dict[str, str] = field(default_factory=dict)


TRANSACTION_COLUMN_MAPPING: dict[ast.Field, list] = {
    ast.Field.ACCOUNT: [Account.name, Account.institution],
    ast.Field.AMOUNT: ["amount"],
    ast.Field.DATE: ["transaction_date"],
    ast.Field.DESCRIPTION: ["description"],
    ast.Field.SECURITY: [
        Security.key,
        Security.name,
        Security.type,
        Security.category,
    ],
    ast.Field.TYPE: [Transaction.type],
}

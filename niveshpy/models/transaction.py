"""Models for financial transactions."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum, auto
from typing import Any

from pydantic import Field as PydanticField
from pydantic import field_validator
from sqlmodel import JSON, NUMERIC, Column, Field, Relationship, SQLModel

from niveshpy.core.query import ast
from niveshpy.models.account import Account
from niveshpy.models.security import Security


class TransactionType(StrEnum):
    """Enum for transaction types."""

    PURCHASE = auto()
    """Transaction type representing purchases.

    This type indicates any amount spent on acquiring securities or assets.
    However, you may use it for other types of transactions as well.
    """
    SALE = auto()
    """Transaction type representing sales.

    This type indicates any amount received from selling securities or assets.
    However, you may use it for other types of transactions as well.
    """


type_format_map = {
    TransactionType.PURCHASE.value: "[green]Purchase",
    TransactionType.SALE.value: "[red]Sale",
}


class TransactionBase(SQLModel):
    """Base model for transactions.

    Attributes:
        transaction_date (date): Date of the transaction.
        type (TransactionType): Type of the transaction.
        description (str): Description of the transaction.
        amount (Decimal): Amount involved in the transaction.
        units (Decimal): Number of units involved in the transaction.
        security_key (str): Foreign key to the associated security.
        account_id (int): Foreign key to the associated account.
        properties (dict[str, Any], optional): Additional properties of the transaction.
            Defaults to an empty dictionary.
    """

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
    """Model for creating transactions.

    Attributes:
        transaction_date (date): Date of the transaction.
        type (TransactionType): Type of the transaction.
        description (str): Description of the transaction.
        amount (Decimal): Amount involved in the transaction.
        units (Decimal): Number of units involved in the transaction.
        security_key (str): Foreign key to the associated security.
        account_id (int): Foreign key to the associated account.
        properties (dict[str, Any], optional): Additional properties of the transaction.
            Defaults to an empty dictionary.
    """


class Transaction(TransactionBase, table=True):
    """Database model for transactions.

    Attributes:
        id (int | None): Primary key ID of the transaction. None if not yet stored in DB.
        transaction_date (date): Date of the transaction.
        type (TransactionType): Type of the transaction.
        description (str): Description of the transaction.
        amount (Decimal): Amount involved in the transaction.
        units (Decimal): Number of units involved in the transaction.
        security_key (str): Foreign key to the associated security.
        security (Security): Related security object.
        account_id (int): Foreign key to the associated account.
        account (Account): Related account object.
        properties (dict[str, Any]): Additional properties of the transaction.
        created (datetime): Timestamp when the transaction was created.
    """

    id: int | None = Field(default=None, primary_key=True)
    security: Security = Relationship()
    account: Account = Relationship()
    created: datetime = Field(default_factory=datetime.now)


class TransactionPublic(TransactionBase):
    """Public model for transactions.

    Attributes:
        id (int): Primary key ID of the transaction.
        transaction_date (date): Date of the transaction.
        type (TransactionType): Type of the transaction.
        description (str): Description of the transaction.
        amount (Decimal): Amount involved in the transaction.
        units (Decimal): Number of units involved in the transaction.
        security_key (str): Foreign key to the associated security.
        account_id (int): Foreign key to the associated account.
        properties (dict[str, Any]): Additional properties of the transaction.
        created (datetime): Timestamp when the transaction was created.
    """

    id: int = Field(
        schema_extra={
            "json_schema_extra": {"style": "dim", "order": 0, "justify": "right"}
        },
    )
    created: datetime = Field(
        schema_extra={"json_schema_extra": {"style": "dim", "order": 9}},
    )


class TransactionDisplay(TransactionPublic):
    """Model for displaying transaction with related info.

    Attributes:
        id (int): Primary key ID of the transaction.
        transaction_date (date): Date of the transaction.
        type (TransactionType): Type of the transaction.
        description (str): Description of the transaction.
        amount (Decimal): Amount involved in the transaction.
        units (Decimal): Number of units involved in the transaction.
        security (str): Formatted security information.
        account (str): Formatted account information.
        properties (dict[str, Any]): Additional properties of the transaction.
        created (datetime): Timestamp when the transaction was created.
    """

    security: str = PydanticField(
        json_schema_extra={"order": 6, "justify": "right"},
    )
    account: str = PydanticField(
        json_schema_extra={"order": 7, "justify": "right", "style": "dim"},
    )

    @field_validator("security", mode="before", json_schema_input_type=str | Security)
    @classmethod
    def validate_security(cls, value: str | Security) -> str:
        """Validate and format the security field.

        Args:
            value (str | Security): The security value to format.

        Returns:
            str: Formatted security string.
        """
        if isinstance(value, Security):
            return f"{value.name} ({value.key})"
        return value

    @field_validator("account", mode="before", json_schema_input_type=str | Account)
    @classmethod
    def validate_account(cls, value: str | Account) -> str:
        """Validate and format the account field.

        Args:
            value (str | Account): The account value to format.

        Returns:
            str: Formatted account string.
        """
        if isinstance(value, Account):
            return f"{value.name} ({value.institution})"
        return value


class TransactionPublicWithRelations(TransactionPublic):
    """Public model for transactions with related account and security info.

    Attributes:
        id (int): Primary key ID of the transaction.
        transaction_date (date): Date of the transaction.
        type (TransactionType): Type of the transaction.
        description (str): Description of the transaction.
        amount (Decimal): Amount involved in the transaction.
        units (Decimal): Number of units involved in the transaction.
        security (Security): Related security object.
        account (Account): Related account object.
        properties (dict[str, Any]): Additional properties of the transaction.
        created (datetime): Timestamp when the transaction was created.
    """

    security: Security = Field(schema_extra={"json_schema_extra": {"order": 6}})
    account: Account = Field(schema_extra={"json_schema_extra": {"order": 7}})


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

"""Models for financial transactions."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum, auto
from typing import Any

from sqlmodel import JSON, NUMERIC, Column, Field, Relationship, SQLModel

from niveshpy.infrastructure.sqlite.models import Account
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

    transaction_date: date
    type: TransactionType
    description: str
    amount: Decimal = Field(sa_column=Column(NUMERIC(24, 2)))
    units: Decimal = Field(sa_column=Column(NUMERIC(24, 3)))
    security_key: str = Field(foreign_key="security.key")
    account_id: int = Field(foreign_key="account.id")
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    def __init_subclass__(cls, **kwargs):
        """Ensure subclasses inherit schema extra metadata."""
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

    id: int
    created: datetime


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

    security: Security
    account: Account


class TransactionPublicWithCost(TransactionPublic):
    """Public model for transactions with cost basis information.

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
        cost (Decimal | None): Cost basis of the transaction.
    """

    cost: Decimal | None = Field()


class TransactionPublicWithRelationsAndCost(TransactionPublicWithRelations):
    """Public model for transactions with related account and security info and cost basis.

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
        cost (Decimal | None): Cost basis of the transaction.
    """

    cost: Decimal | None

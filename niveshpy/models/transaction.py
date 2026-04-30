"""Models for financial transactions."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum, auto
from typing import Any

from attrs import field, frozen

from niveshpy.models.account import AccountPublic
from niveshpy.models.security import SecurityPublic


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


@frozen
class TransactionCreate:
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

    transaction_date: date
    type: TransactionType
    description: str
    amount: Decimal
    units: Decimal
    security_key: str
    account_id: int
    properties: Mapping[str, Any] = field(factory=dict)


@frozen
class TransactionPublic:
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
        properties (Mapping[str, Any]): Additional properties of the transaction.
        created (datetime): Timestamp when the transaction was created.
        security (SecurityPublic | None): Related security object, if available.
        account (AccountPublic | None): Related account object, if available.
        cost (Decimal | None): Cost basis of the transaction, if applicable.
        source (str | None): Source of the transaction, extracted from properties if available.
    """

    id: int
    transaction_date: date
    type: TransactionType
    description: str
    amount: Decimal
    units: Decimal
    security_key: str
    account_id: int
    properties: Mapping[str, Any]
    created: datetime
    cost: Decimal | None = None
    security: SecurityPublic | None = None
    account: AccountPublic | None = None
    source: str | None = field(init=False)

    def __attrs_post_init__(self):
        """Set the source field based on properties after initialization."""
        object.__setattr__(self, "source", self.properties.get("source"))

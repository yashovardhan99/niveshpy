"""SQLite models for NiveshPy."""

import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import (
    JSON,
    NUMERIC,
    Column,
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
)

from niveshpy.exceptions import InvalidInputError
from niveshpy.models.account import AccountPublic
from niveshpy.models.price import PricePublic
from niveshpy.models.security import SecurityCategory, SecurityPublic, SecurityType
from niveshpy.models.transaction import TransactionPublic, TransactionType


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
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    def to_public(self) -> AccountPublic:
        """Convert an Account database model to an AccountPublic domain model."""
        if self.id is None:
            raise InvalidInputError(self, "Account ID cannot be None")
        return AccountPublic(
            id=self.id,
            name=self.name,
            institution=self.institution,
            properties=self.properties,
            created_at=self.created_at,
        )


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
    created: datetime.datetime = Field(default_factory=datetime.datetime.now)

    def to_public(self) -> SecurityPublic:
        """Convert a Security database model to a SecurityPublic domain model."""
        return SecurityPublic(
            key=self.key,
            name=self.name,
            type=self.type,
            category=self.category,
            properties=self.properties,
            created=self.created,
        )


class Price(SQLModel, table=True):
    """Database model for price data.

    Attributes:
        security_key (str): Foreign key to the associated security.
        security (Security): Related security object.
        date (datetime.date): Date of the price data.
        open (Decimal): Opening price.
        high (Decimal): Highest price.
        low (Decimal): Lowest price.
        close (Decimal): Closing price.
        properties (dict[str, Any]): Additional properties of the price data.
        created (datetime.datetime): Timestamp when the price data was created.
    """

    security_key: str = Field(foreign_key="security.key", primary_key=True)
    security: Security = Relationship()
    date: datetime.date = Field(primary_key=True)
    open: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    high: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    low: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    close: Decimal = Field(sa_column=Column(NUMERIC(24, 4)))
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created: datetime.datetime = Field(
        default_factory=datetime.datetime.now, title="Created"
    )

    def to_public(self, *, include_security: bool = True) -> PricePublic:
        """Convert a Price database model to a PricePublic domain model."""
        return PricePublic(
            security_key=self.security_key,
            date=self.date,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            properties=self.properties,
            created=self.created,
            security=self.security.to_public() if include_security else None,
        )


class Transaction(SQLModel, table=True):
    """Database model for transactions.

    Attributes:
        id (int | None): Primary key ID of the transaction. None if not yet stored in DB.
        transaction_date (datetime.date): Date of the transaction.
        type (TransactionType): Type of the transaction.
        description (str): Description of the transaction.
        amount (Decimal): Amount involved in the transaction.
        units (Decimal): Number of units involved in the transaction.
        security_key (str): Foreign key to the associated security.
        security (Security): Related security object.
        account_id (int): Foreign key to the associated account.
        account (Account): Related account object.
        properties (dict[str, Any]): Additional properties of the transaction.
        created (datetime.datetime): Timestamp when the transaction was created.
    """

    id: int | None = Field(default=None, primary_key=True)
    transaction_date: datetime.date
    type: TransactionType
    description: str
    amount: Decimal = Field(sa_column=Column(NUMERIC(24, 2)))
    units: Decimal = Field(sa_column=Column(NUMERIC(24, 3)))
    security_key: str = Field(foreign_key="security.key")
    security: Security = Relationship()
    account_id: int = Field(foreign_key="account.id")
    account: Account = Relationship()
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created: datetime.datetime = Field(default_factory=datetime.datetime.now)

    def to_public(self, *, include_relations: bool = True) -> TransactionPublic:
        """Convert a Transaction database model to a TransactionPublic domain model."""
        if self.id is None:
            raise InvalidInputError(self, "Transaction ID cannot be None")
        return TransactionPublic(
            id=self.id,
            transaction_date=self.transaction_date,
            type=self.type,
            description=self.description,
            amount=self.amount,
            units=self.units,
            security_key=self.security_key,
            account_id=self.account_id,
            properties=self.properties,
            created=self.created,
            security=self.security.to_public() if include_relations else None,
            account=self.account.to_public() if include_relations else None,
        )

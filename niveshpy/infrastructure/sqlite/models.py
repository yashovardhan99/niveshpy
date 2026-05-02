"""SQLite models for NiveshPy."""

import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    NUMERIC,
    DateTime,
    Enum,
    ForeignKey,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from niveshpy.exceptions import InvalidInputError
from niveshpy.models.account import AccountPublic
from niveshpy.models.price import PricePublic
from niveshpy.models.security import SecurityCategory, SecurityPublic, SecurityType
from niveshpy.models.transaction import TransactionPublic, TransactionType


class TZDateTime(TypeDecorator):
    """Custom SQLAlchemy type to handle timezone-aware datetimes in SQLite."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert timezone-aware datetime to UTC naive datetime for storage."""
        if value is not None:
            if not value.tzinfo or value.tzinfo.utcoffset(value) is None:
                raise TypeError("tzinfo is required")
            value = value.astimezone(datetime.UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        """Convert stored UTC naive datetime back to timezone-aware datetime."""
        if value is not None:
            value = value.replace(tzinfo=datetime.UTC)
        return value


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class Account(Base):
    """Database model for investment accounts.

    Attributes:
        id (int): Primary key ID of the account.
        name (str): Name of the account.
        institution (str): Financial institution managing the account.
        properties (dict[str, Any]): Additional properties of the account.
        created_at (datetime): Timestamp when the account was created.
    """

    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("name", "institution", name="uix_name_institution"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    institution: Mapped[str]
    properties: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TZDateTime, server_default=func.current_timestamp()
    )

    def to_public(self) -> AccountPublic:
        """Convert an Account database model to an AccountPublic domain model."""
        if self.id is None:
            raise InvalidInputError(self, "Account ID cannot be None")
        return AccountPublic(
            id=self.id,
            name=self.name,
            institution=self.institution,
            properties=self.properties,
            created=self.created_at.astimezone().replace(tzinfo=None),
        )


class Security(Base):
    """Database model for securities.

    Attributes:
        key (str): Unique key identifying the security.
        name (str): Name of the security.
        type (SecurityType): Type of the security.
        category (SecurityCategory): Category of the security.
        properties (dict[str, Any]): Additional properties of the security.
        created (datetime): Timestamp when the security was created.
    """

    __tablename__ = "security"

    key: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    type: Mapped[SecurityType] = mapped_column(
        Enum(
            SecurityType,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        )
    )
    category: Mapped[SecurityCategory] = mapped_column(
        Enum(
            SecurityCategory,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        )
    )
    properties: Mapped[dict[str, Any]] = mapped_column(JSON)
    created: Mapped[datetime.datetime] = mapped_column(
        TZDateTime, server_default=func.current_timestamp()
    )

    def to_public(self) -> SecurityPublic:
        """Convert a Security database model to a SecurityPublic domain model."""
        return SecurityPublic(
            key=self.key,
            name=self.name,
            type=self.type,
            category=self.category,
            properties=self.properties,
            created=self.created.astimezone().replace(tzinfo=None),
        )


class Price(Base):
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

    __tablename__ = "price"

    security_key: Mapped[str] = mapped_column(
        ForeignKey("security.key"), primary_key=True
    )
    security: Mapped[Security] = relationship()
    date: Mapped[datetime.date] = mapped_column(primary_key=True)
    open: Mapped[Decimal] = mapped_column(NUMERIC(24, 4))
    high: Mapped[Decimal] = mapped_column(NUMERIC(24, 4))
    low: Mapped[Decimal] = mapped_column(NUMERIC(24, 4))
    close: Mapped[Decimal] = mapped_column(NUMERIC(24, 4))
    properties: Mapped[dict[str, Any]] = mapped_column(JSON)
    created: Mapped[datetime.datetime] = mapped_column(
        TZDateTime, server_default=func.current_timestamp()
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
            created=self.created.astimezone().replace(tzinfo=None),
            security=self.security.to_public() if include_security else None,
        )


class Transaction(Base):
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

    __tablename__ = "transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_date: Mapped[datetime.date] = mapped_column()
    type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        )
    )
    description: Mapped[str] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(NUMERIC(24, 2))
    units: Mapped[Decimal] = mapped_column(NUMERIC(24, 3))
    security_key: Mapped[str] = mapped_column(ForeignKey("security.key"))
    security: Mapped[Security] = relationship()
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    account: Mapped[Account] = relationship()
    properties: Mapped[dict[str, Any]] = mapped_column(JSON)
    created: Mapped[datetime.datetime] = mapped_column(
        TZDateTime, server_default=func.current_timestamp()
    )

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
            created=self.created.astimezone().replace(tzinfo=None),
            security=self.security.to_public() if include_relations else None,
            account=self.account.to_public() if include_relations else None,
        )

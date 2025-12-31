"""Tests for all transaction models."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from niveshpy.models.account import Account
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.models.transaction import (
    Transaction,
    TransactionCreate,
    TransactionDisplay,
    TransactionType,
)


class TestTransactionModels:
    """Pure model validation tests (no database)."""

    # Happy path tests

    def test_transaction_create_with_required_fields(self):
        """Test creating a TransactionCreate with all required fields."""
        transaction = TransactionCreate(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Bought mutual fund units",
            amount=Decimal("10000.50"),
            units=Decimal("100.500"),
            security_key="123456",
            account_id=1,
        )
        assert transaction.transaction_date == date(2024, 1, 15)
        assert transaction.type == TransactionType.PURCHASE
        assert transaction.description == "Bought mutual fund units"
        assert transaction.amount == Decimal("10000.50")
        assert transaction.units == Decimal("100.500")
        assert transaction.security_key == "123456"
        assert transaction.account_id == 1
        assert transaction.properties == {}

    def test_transaction_create_with_properties(self):
        """Test creating a TransactionCreate with properties."""
        transaction = TransactionCreate(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.SALE,
            description="Sold stock",
            amount=Decimal("5000.00"),
            units=Decimal("50.000"),
            security_key="AAPL",
            account_id=2,
            properties={"broker": "Zerodha", "order_id": "ORD123"},
        )
        assert transaction.properties["broker"] == "Zerodha"
        assert transaction.properties["order_id"] == "ORD123"

    def test_transaction_instance_creation(self):
        """Test creating a Transaction instance."""
        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test transaction",
            amount=Decimal("1000.00"),
            units=Decimal("10.000"),
            security_key="TEST",
            account_id=1,
        )
        assert transaction.id is None
        assert transaction.type == TransactionType.PURCHASE

    # Enum validation tests

    def test_transaction_all_types_valid(self):
        """Test all TransactionType enum values are valid."""
        for txn_type in TransactionType:
            transaction = TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=txn_type,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )
            assert transaction.type == txn_type

    def test_transaction_invalid_type_string(self):
        """Test that invalid type string raises ValidationError."""
        with pytest.raises(ValidationError, match="input_value='INVALID_TYPE'"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type="INVALID_TYPE",
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )

    # Required field validation tests

    def test_transaction_create_missing_date(self):
        """Test creating TransactionCreate without date raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            TransactionCreate(
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )

    def test_transaction_create_missing_type(self):
        """Test creating TransactionCreate without type raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )

    def test_transaction_create_missing_description(self):
        """Test creating TransactionCreate without description raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )

    def test_transaction_create_missing_amount(self):
        """Test creating TransactionCreate without amount raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )

    def test_transaction_create_missing_units(self):
        """Test creating TransactionCreate without units raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                security_key="TEST",
                account_id=1,
            )

    def test_transaction_create_missing_security_key(self):
        """Test creating TransactionCreate without security_key raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                account_id=1,
            )

    def test_transaction_create_missing_account_id(self):
        """Test creating TransactionCreate without account_id raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
            )

    # Type validation tests

    def test_transaction_wrong_type_date(self):
        """Test creating TransactionCreate with wrong type for date."""
        with pytest.raises(ValidationError, match="Input should be a valid date"):
            TransactionCreate(
                transaction_date="not-a-date",
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )

    def test_transaction_wrong_type_amount(self):
        """Test creating TransactionCreate with wrong type for amount."""
        with pytest.raises(ValidationError):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                amount="not-a-number",
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )

    def test_transaction_wrong_type_units(self):
        """Test creating TransactionCreate with wrong type for units."""
        with pytest.raises(ValidationError):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                units="not-a-number",
                security_key="TEST",
                account_id=1,
            )

    def test_transaction_wrong_type_security_key(self):
        """Test creating TransactionCreate with wrong type for security_key."""
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key=123456,
                account_id=1,
            )

    def test_transaction_wrong_type_account_id(self):
        """Test creating TransactionCreate with wrong type for account_id."""
        with pytest.raises(ValidationError, match="Input should be a valid integer"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id="not-an-int",
            )

    def test_transaction_properties_must_be_dict(self):
        """Test that properties must be a dict."""
        with pytest.raises(ValidationError, match="Input should be a valid dictionary"):
            TransactionCreate(
                transaction_date=date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
                properties="not_a_dict",
            )

    # Decimal precision tests

    def test_transaction_decimal_from_string(self):
        """Test creating TransactionCreate with Decimal from string."""
        transaction = TransactionCreate(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("12345.67"),
            units=Decimal("100.123"),
            security_key="TEST",
            account_id=1,
        )
        assert transaction.amount == Decimal("12345.67")
        assert transaction.units == Decimal("100.123")

    def test_transaction_decimal_from_float(self):
        """Test creating TransactionCreate with Decimal from float (will convert)."""
        transaction = TransactionCreate(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=100.50,
            units=10.5,
            security_key="TEST",
            account_id=1,
        )
        assert isinstance(transaction.amount, Decimal)
        assert isinstance(transaction.units, Decimal)

    def test_transaction_large_decimal_values(self):
        """Test TransactionCreate with large Decimal values."""
        transaction = TransactionCreate(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Large transaction",
            amount=Decimal("999999999999999999999999.99"),
            units=Decimal("999999999999999999999.999"),
            security_key="TEST",
            account_id=1,
        )
        assert transaction.amount > 0
        assert transaction.units > 0

    # Edge cases

    def test_transaction_empty_properties_dict(self):
        """Test creating TransactionCreate with empty properties dict."""
        transaction = TransactionCreate(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key="TEST",
            account_id=1,
            properties={},
        )
        assert transaction.properties == {}

    def test_transaction_nested_properties(self):
        """Test creating TransactionCreate with nested properties."""
        props = {
            "trade_details": {"broker": "Zerodha", "charges": 15.50},
            "tags": ["sip", "monthly"],
        }
        transaction = TransactionCreate(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key="TEST",
            account_id=1,
            properties=props,
        )
        assert transaction.properties["trade_details"]["broker"] == "Zerodha"
        assert "sip" in transaction.properties["tags"]

    def test_transaction_unicode_description(self):
        """Test creating TransactionCreate with unicode description."""
        transaction = TransactionCreate(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="म्यूचुअल फंड खरीदा",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key="TEST",
            account_id=1,
        )
        assert transaction.description == "म्यूचुअल फंड खरीदा"

    def test_transaction_date_string_conversion(self):
        """Test that date strings are converted to date objects."""
        transaction = TransactionCreate(
            transaction_date="2024-01-15",
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key="TEST",
            account_id=1,
        )
        assert transaction.transaction_date == date(2024, 1, 15)
        assert isinstance(transaction.transaction_date, date)


class TestTransactionDatabase:
    """Database integration tests with foreign key constraints."""

    # Database persistence tests

    def test_transaction_insert_and_retrieve(self, session):
        """Test inserting and retrieving a Transaction from database."""
        # Create prerequisite account and security
        account = Account(name="Test Account", institution="Test Bank")
        security = Security(
            key="TEST123",
            name="Test Security",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add(account)
        session.add(security)
        session.commit()

        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test transaction",
            amount=Decimal("10000.50"),
            units=Decimal("100.500"),
            security_key=security.key,
            account_id=account.id,
        )
        session.add(transaction)
        session.commit()

        assert transaction.id is not None

        retrieved = session.get(Transaction, transaction.id)
        assert retrieved is not None
        assert retrieved.description == "Test transaction"
        assert retrieved.amount == Decimal("10000.50")
        assert retrieved.units == Decimal("100.500")
        assert retrieved.security_key == "TEST123"
        assert retrieved.account_id == account.id

    def test_transaction_auto_generated_id(self, session):
        """Test that the Transaction ID is auto-generated upon insertion."""
        account = Account(name="Test Account", institution="Test Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key=security.key,
            account_id=account.id,
        )
        assert transaction.id is None

        session.add(transaction)
        session.commit()

        assert transaction.id is not None
        assert isinstance(transaction.id, int)

    def test_transaction_created_timestamp_auto_set(self, session):
        """Test that created timestamp is auto-set upon insertion."""
        account = Account(name="Test Account", institution="Test Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        before = datetime.now()
        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key=security.key,
            account_id=account.id,
        )
        session.add(transaction)
        session.commit()
        after = datetime.now()

        assert before <= transaction.created <= after

    # Foreign key constraint tests

    @pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")
    def test_transaction_invalid_security_key_fails(self, session):
        """Test that invalid security_key raises IntegrityError."""
        account = Account(name="Test Account", institution="Test Bank")
        session.add(account)
        session.commit()

        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key="NONEXISTENT",
            account_id=account.id,
        )
        session.add(transaction)

        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            session.commit()

    @pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")
    def test_transaction_invalid_account_id_fails(self, session):
        """Test that invalid account_id raises IntegrityError."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add(security)
        session.commit()

        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key=security.key,
            account_id=99999,
        )
        session.add(transaction)

        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            session.commit()

    # Relationship tests

    def test_transaction_security_relationship(self, session):
        """Test that Transaction.security relationship loads correctly."""
        account = Account(name="Test Account", institution="Test Bank")
        security = Security(
            key="REL123",
            name="Reliance Industries",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Bought Reliance",
            amount=Decimal("5000.00"),
            units=Decimal("50.000"),
            security_key=security.key,
            account_id=account.id,
        )
        session.add(transaction)
        session.commit()
        transaction_id = transaction.id
        session.expunge_all()

        retrieved = session.get(Transaction, transaction_id)
        assert retrieved.security is not None
        assert retrieved.security.name == "Reliance Industries"
        assert retrieved.security.key == "REL123"

    def test_transaction_account_relationship(self, session):
        """Test that Transaction.account relationship loads correctly."""
        account = Account(name="HDFC Savings", institution="HDFC Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("1000.00"),
            units=Decimal("10.000"),
            security_key=security.key,
            account_id=account.id,
        )
        session.add(transaction)
        session.commit()
        transaction_id = transaction.id
        session.expunge_all()

        retrieved = session.get(Transaction, transaction_id)
        assert retrieved.account is not None
        assert retrieved.account.name == "HDFC Savings"
        assert retrieved.account.institution == "HDFC Bank"

    # Decimal precision persistence tests

    def test_transaction_amount_precision_persists(self, session):
        """Test that amount precision (24,2) is preserved."""
        account = Account(name="Test", institution="Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Precision test",
            amount=Decimal("12345.67"),
            units=Decimal("100.123"),
            security_key=security.key,
            account_id=account.id,
        )
        session.add(transaction)
        session.commit()
        transaction_id = transaction.id
        session.expunge_all()

        retrieved = session.get(Transaction, transaction_id)
        assert retrieved.amount == Decimal("12345.67")

    def test_transaction_units_precision_persists(self, session):
        """Test that units precision (24,3) is preserved."""
        account = Account(name="Test", institution="Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Precision test",
            amount=Decimal("1000.00"),
            units=Decimal("99.999"),
            security_key=security.key,
            account_id=account.id,
        )
        session.add(transaction)
        session.commit()
        transaction_id = transaction.id
        session.expunge_all()

        retrieved = session.get(Transaction, transaction_id)
        assert retrieved.units == Decimal("99.999")

    # Enum persistence tests

    def test_transaction_type_persists_correctly(self, session):
        """Test that TransactionType enum persists and retrieves correctly."""
        account = Account(name="Test", institution="Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        for txn_type in TransactionType:
            transaction = Transaction(
                transaction_date=date(2024, 1, 15),
                type=txn_type,
                description=f"Test {txn_type.value}",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key=security.key,
                account_id=account.id,
            )
            session.add(transaction)
        session.commit()
        session.expunge_all()

        transactions = session.exec(select(Transaction)).all()
        retrieved_types = {t.type for t in transactions}
        assert retrieved_types == set(TransactionType)

    # JSON properties tests

    def test_transaction_properties_persist_as_json(self, session):
        """Test that properties are persisted and retrieved correctly as JSON."""
        account = Account(name="Test", institution="Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        props = {"broker": "Zerodha", "order_id": "ORD123"}
        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("1000.00"),
            units=Decimal("10.000"),
            security_key=security.key,
            account_id=account.id,
            properties=props,
        )
        session.add(transaction)
        session.commit()
        transaction_id = transaction.id
        session.expunge_all()

        retrieved = session.get(Transaction, transaction_id)
        assert retrieved.properties == props

    def test_transaction_complex_properties_persist(self, session):
        """Test that complex properties persist correctly."""
        account = Account(name="Test", institution="Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        props = {
            "trade_metadata": {"exchange": "NSE", "segment": "EQ", "charges": 25.50},
            "tags": ["long-term", "equity"],
            "notes": {"analyst": "John", "rating": 5},
        }
        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Complex properties test",
            amount=Decimal("5000.00"),
            units=Decimal("50.000"),
            security_key=security.key,
            account_id=account.id,
            properties=props,
        )
        session.add(transaction)
        session.commit()
        transaction_id = transaction.id
        session.expunge_all()

        retrieved = session.get(Transaction, transaction_id)
        assert retrieved.properties["trade_metadata"]["exchange"] == "NSE"
        assert "long-term" in retrieved.properties["tags"]
        assert retrieved.properties["notes"]["rating"] == 5

    # Multiple transactions test

    def test_multiple_transactions_same_security_and_account(self, session):
        """Test inserting multiple transactions for same security and account."""
        account = Account(name="Test", institution="Bank")
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add_all([account, security])
        session.commit()

        transactions = [
            Transaction(
                transaction_date=date(2024, 1, i),
                type=TransactionType.PURCHASE,
                description=f"Purchase {i}",
                amount=Decimal(f"{i * 100}.00"),
                units=Decimal(f"{i}.000"),
                security_key=security.key,
                account_id=account.id,
            )
            for i in range(1, 6)
        ]
        session.add_all(transactions)
        session.commit()

        retrieved_transactions = session.exec(select(Transaction)).all()
        assert len(retrieved_transactions) == 5
        assert all(t.security_key == "TEST" for t in retrieved_transactions)
        assert all(t.account_id == account.id for t in retrieved_transactions)


class TestTransactionDisplay:
    """Tests for TransactionDisplay model with field validators."""

    def test_transaction_display_security_validator_with_object(self):
        """Test that TransactionDisplay formats Security object to string."""
        security = Security(
            key="TEST123",
            name="Test Mutual Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )

        transaction = TransactionDisplay(
            id=1,
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("1000.00"),
            units=Decimal("10.000"),
            security=security,  # Pass Security object
            account="Test Account (Test Bank)",
            security_key="TEST123",
            account_id=1,
            created=datetime.now(),
        )

        assert transaction.security == "Test Mutual Fund (TEST123)"

    def test_transaction_display_security_validator_with_string(self):
        """Test that TransactionDisplay keeps string security as-is."""
        transaction = TransactionDisplay(
            id=1,
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("1000.00"),
            units=Decimal("10.000"),
            security="Already Formatted Security",
            account="Test Account",
            security_key="TEST",
            account_id=1,
            created=datetime.now(),
        )

        assert transaction.security == "Already Formatted Security"

    def test_transaction_display_account_validator_with_object(self):
        """Test that TransactionDisplay formats Account object to string."""
        account = Account(name="HDFC Savings", institution="HDFC Bank")
        account.id = 1

        transaction = TransactionDisplay(
            id=1,
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("1000.00"),
            units=Decimal("10.000"),
            security="Test Security (TEST)",
            account=account,  # Pass Account object
            security_key="TEST",
            account_id=1,
            created=datetime.now(),
        )

        assert transaction.account == "HDFC Savings (HDFC Bank)"

    def test_transaction_display_account_validator_with_string(self):
        """Test that TransactionDisplay keeps string account as-is."""
        transaction = TransactionDisplay(
            id=1,
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Test",
            amount=Decimal("1000.00"),
            units=Decimal("10.000"),
            security="Test Security",
            account="Already Formatted Account",
            security_key="TEST",
            account_id=1,
            created=datetime.now(),
        )

        assert transaction.account == "Already Formatted Account"

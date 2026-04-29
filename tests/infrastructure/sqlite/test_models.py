"""Tests for SQLite models."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from niveshpy.infrastructure.sqlite.models import Account, Price, Security, Transaction
from niveshpy.models.security import SecurityCategory, SecurityCreate, SecurityType
from niveshpy.models.transaction import TransactionType


class TestAccountModels:
    """Tests for account models.

    These are pure model validation tests and do not interact with the database.
    """

    # Happy path tests

    def test_account_create_with_required_fields(self):
        """Test creating an Account instance with required fields only."""
        account = Account(name="HDFC Savings", institution="HDFC Bank")
        assert account.name == "HDFC Savings"
        assert account.institution == "HDFC Bank"
        assert account.properties == {}

    def test_account_create_with_properties(self):
        """Test creating an Account instance with properties."""
        account = Account(
            name="Investment Account",
            institution="Zerodha",
            properties={"account_type": "demat", "number": "ZD1234"},
        )
        assert account.properties["account_type"] == "demat"
        assert account.properties["number"] == "ZD1234"

    def test_account_instance_creation(self):
        """Test creating an Account instance."""
        account = Account(name="SBI", institution="State Bank")
        assert account.name == "SBI"
        assert account.id is None  # Not yet persisted

    # Edge cases

    def test_account_empty_properties_dict(self):
        """Test creating an Account instance with empty properties dict."""
        account = Account(name="A", institution="B", properties={})
        assert account.properties == {}

    def test_account_nested_properties(self):
        """Test creating an Account instance with nested properties."""
        props = {
            "details": {"type": "savings", "currency": "INR"},
            "tags": ["primary", "active"],
        }
        account = Account(name="A", institution="B", properties=props)
        assert account.properties["details"]["currency"] == "INR"
        assert "primary" in account.properties["tags"]

    def test_account_unicode_characters(self):
        """Test creating an Account instance with unicode characters."""
        account = Account(name="बचत खाता", institution="भारतीय स्टेट बैंक")
        assert account.name == "बचत खाता"

    def test_account_special_characters(self):
        """Test creating an Account instance with special characters."""
        account = Account(name="Account #1", institution="Bank & Co.")
        assert "#1" in account.name
        assert "&" in account.institution


class TestAccountDatabase:
    """Tests for Account database model."""

    # Database persistence tests
    def test_account_insert_and_retrieve(self, session):
        """Test inserting and retrieving an Account from the database."""
        account = Account(name="HDFC", institution="Bank")
        session.add(account)
        session.commit()

        assert account.id is not None

        retrieved = session.get(Account, account.id)
        assert retrieved.name == "HDFC"
        assert retrieved.institution == "Bank"

    def test_account_auto_generated_id(self, session):
        """Test that the Account ID is auto-generated upon insertion."""
        account = Account(name="Test", institution="Bank")
        assert account.id is None

        session.add(account)
        session.commit()

        assert account.id is not None
        assert isinstance(account.id, int)

    def test_account_created_at_auto_set(self, session):
        """Test that the created_at timestamp is auto-set upon insertion."""
        before = datetime.now()
        account = Account(name="Test", institution="Bank")
        session.add(account)
        session.commit()
        after = datetime.now()

        assert before <= account.created_at <= after

    # Unique constraint tests
    @pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")
    def test_account_unique_constraint_violation(self, session):
        """Test that inserting duplicate Account violates unique constraint."""
        account1 = Account(name="Savings", institution="HDFC")
        session.add(account1)
        session.commit()

        account2 = Account(name="Savings", institution="HDFC")
        session.add(account2)

        with pytest.raises(IntegrityError, match="UNIQUE constraint failed"):
            session.commit()

    def test_account_same_name_different_institution(self, session):
        """Test inserting Accounts with same name but different institutions."""
        account1 = Account(name="Savings", institution="HDFC")
        account2 = Account(name="Savings", institution="ICICI")

        session.add(account1)
        session.add(account2)
        session.commit()

        assert account1.id != account2.id

    def test_account_different_name_same_institution(self, session):
        """Test inserting Accounts with different names but same institution."""
        account1 = Account(name="Savings", institution="HDFC")
        account2 = Account(name="Current", institution="HDFC")

        session.add(account1)
        session.add(account2)
        session.commit()

        assert account1.id != account2.id

    # JSON properties tests
    def test_account_properties_persist_as_json(self, session):
        """Test that Account properties are persisted and retrieved correctly as JSON."""
        props = {"folio": "ABC123", "branch": "Mumbai"}
        account = Account(name="Test", institution="Bank", properties=props)

        session.add(account)
        session.commit()
        account_id = account.id
        session.expunge_all()

        retrieved = session.get(Account, account_id)
        assert retrieved.properties == props

    def test_account_complex_properties_persist(self, session):
        """Test that complex Account properties are persisted and retrieved correctly as JSON."""
        props = {
            "metadata": {"created_by": "user1", "version": 2},
            "tags": ["primary", "active"],
            "balance": 50000.50,
        }
        account = Account(name="Test", institution="Bank", properties=props)

        session.add(account)
        session.commit()
        account_id = account.id
        session.expunge_all()

        retrieved = session.get(Account, account_id)
        assert retrieved.properties["tags"] == ["primary", "active"]
        assert retrieved.properties["balance"] == 50000.50


class TestSecurityModels:
    """Pure model validation tests (no database)."""

    # Happy path tests

    def test_security_create_with_required_fields(self):
        """Test creating a SecurityCreate with all required fields."""
        security = SecurityCreate(
            key="123456",
            name="HDFC Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        assert security.key == "123456"
        assert security.name == "HDFC Equity Fund"
        assert security.type == SecurityType.MUTUAL_FUND
        assert security.category == SecurityCategory.EQUITY
        assert security.properties == {}

    def test_security_create_with_properties(self):
        """Test creating a SecurityCreate with properties."""
        security = SecurityCreate(
            key="AAPL",
            name="Apple Inc.",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={"exchange": "NASDAQ", "sector": "Technology"},
        )
        assert security.properties["exchange"] == "NASDAQ"
        assert security.properties["sector"] == "Technology"

    def test_security_instance_creation(self):
        """Test creating a Security instance."""
        security = Security(
            key="BOND001",
            name="Government Bond",
            type=SecurityType.BOND,
            category=SecurityCategory.DEBT,
        )
        assert security.key == "BOND001"
        assert security.type == SecurityType.BOND

    # Enum validation tests

    def test_security_all_types_valid(self):
        """Test all SecurityType enum values are valid."""
        for sec_type in SecurityType:
            security = SecurityCreate(
                key="TEST",
                name="Test Security",
                type=sec_type,
                category=SecurityCategory.OTHER,
            )
            assert security.type == sec_type

    def test_security_all_categories_valid(self):
        """Test all SecurityCategory enum values are valid."""
        for category in SecurityCategory:
            security = SecurityCreate(
                key="TEST",
                name="Test Security",
                type=SecurityType.OTHER,
                category=category,
            )
            assert security.category == category

    # Edge cases

    def test_security_empty_properties_dict(self):
        """Test creating SecurityCreate with empty properties dict."""
        security = SecurityCreate(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
        )
        assert security.properties == {}

    def test_security_nested_properties(self):
        """Test creating SecurityCreate with nested properties."""
        props = {
            "metadata": {"isin": "INE009A01021", "sector": "Banking"},
            "tags": ["large-cap", "dividend"],
        }
        security = SecurityCreate(
            key="HDFC",
            name="HDFC Bank",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties=props,
        )
        assert security.properties["metadata"]["isin"] == "INE009A01021"
        assert "large-cap" in security.properties["tags"]

    def test_security_unicode_characters(self):
        """Test creating SecurityCreate with unicode characters."""
        security = SecurityCreate(
            key="TEST",
            name="भारतीय म्यूचुअल फंड",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        assert security.name == "भारतीय म्यूचुअल फंड"

    def test_security_special_characters_in_name(self):
        """Test creating SecurityCreate with special characters."""
        security = SecurityCreate(
            key="TEST",
            name="Fund & Co. (Growth)",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        assert "&" in security.name
        assert "(" in security.name


class TestSecurityDatabase:
    """Database integration tests."""

    # Database persistence tests

    def test_security_insert_and_retrieve(self, session):
        """Test inserting and retrieving a Security from database."""
        security = Security(
            key="123456",
            name="HDFC Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        session.add(security)
        session.commit()

        retrieved = session.get(Security, "123456")
        assert retrieved is not None
        assert retrieved.name == "HDFC Equity Fund"
        assert retrieved.type == SecurityType.MUTUAL_FUND

    def test_security_created_timestamp_auto_set(self, session):
        """Test that created timestamp is auto-set upon insertion."""
        from datetime import datetime

        before = datetime.now()
        security = Security(
            key="TEST",
            name="Test Security",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add(security)
        session.commit()
        after = datetime.now()

        assert before <= security.created <= after

    # Unique constraint tests (key is primary key)

    @pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")
    def test_security_duplicate_key_violation(self, session):
        """Test that duplicate key raises IntegrityError."""
        security1 = Security(
            key="DUPLICATE",
            name="First Security",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add(security1)
        session.commit()

        security2 = Security(
            key="DUPLICATE",
            name="Second Security",
            type=SecurityType.BOND,
            category=SecurityCategory.DEBT,
        )
        session.add(security2)

        with pytest.raises(IntegrityError, match="UNIQUE constraint failed"):
            session.commit()

    def test_security_different_keys_same_name_allowed(self, session):
        """Test that different keys with same name are allowed."""
        security1 = Security(
            key="KEY1",
            name="Common Name",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        security2 = Security(
            key="KEY2",
            name="Common Name",
            type=SecurityType.BOND,
            category=SecurityCategory.DEBT,
        )

        session.add(security1)
        session.add(security2)
        session.commit()

        assert session.get(Security, "KEY1").name == "Common Name"
        assert session.get(Security, "KEY2").name == "Common Name"

    # Enum persistence tests

    def test_security_type_persists_correctly(self, session):
        """Test that SecurityType enum persists and retrieves correctly."""
        for sec_type in SecurityType:
            security = Security(
                key=f"TYPE_{sec_type.value}",
                name=f"Test {sec_type.value}",
                type=sec_type,
                category=SecurityCategory.OTHER,
            )
            session.add(security)
        session.commit()
        session.expunge_all()

        for sec_type in SecurityType:
            retrieved = session.get(Security, f"TYPE_{sec_type.value}")
            assert retrieved.type == sec_type

    def test_security_category_persists_correctly(self, session):
        """Test that SecurityCategory enum persists and retrieves correctly."""
        for category in SecurityCategory:
            security = Security(
                key=f"CAT_{category.value}",
                name=f"Test {category.value}",
                type=SecurityType.OTHER,
                category=category,
            )
            session.add(security)
        session.commit()
        session.expunge_all()

        for category in SecurityCategory:
            retrieved = session.get(Security, f"CAT_{category.value}")
            assert retrieved.category == category

    # JSON properties tests

    def test_security_properties_persist_as_json(self, session):
        """Test that properties are persisted and retrieved correctly as JSON."""
        props = {"isin": "INE001A01036", "exchange": "NSE"}
        security = Security(
            key="RELI",
            name="Reliance Industries",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties=props,
        )

        session.add(security)
        session.commit()
        session.expunge_all()

        retrieved = session.get(Security, "RELI")
        assert retrieved.properties == props

    def test_security_complex_properties_persist(self, session):
        """Test that complex properties persist correctly."""
        props = {
            "fund_details": {
                "aum": 50000.5,
                "expense_ratio": 1.25,
                "launch_date": "2020-01-01",
            },
            "holdings": ["RELIANCE", "TCS", "HDFC"],
            "ratings": {"morningstar": 5, "crisil": 4},
        }
        security = Security(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            properties=props,
        )

        session.add(security)
        session.commit()
        session.expunge_all()

        retrieved = session.get(Security, "MF001")
        assert retrieved.properties["fund_details"]["aum"] == 50000.5
        assert "TCS" in retrieved.properties["holdings"]
        assert retrieved.properties["ratings"]["morningstar"] == 5


class TestPriceDatabase:
    """Database integration tests with composite primary key."""

    # Database persistence tests

    def test_price_insert_and_retrieve(self, session):
        """Test inserting and retrieving a Price from database."""
        # Create prerequisite security
        security = Security(
            key="TEST123",
            name="Test Security",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        price = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("100.5000"),
            high=Decimal("105.7500"),
            low=Decimal("99.2500"),
            close=Decimal("103.0000"),
        )
        session.add(price)
        session.commit()

        # Retrieve using composite primary key
        retrieved = session.get(
            Price, {"security_key": "TEST123", "date": date(2024, 1, 15)}
        )
        assert retrieved is not None
        assert retrieved.open == Decimal("100.5000")
        assert retrieved.high == Decimal("105.7500")
        assert retrieved.low == Decimal("99.2500")
        assert retrieved.close == Decimal("103.0000")

    def test_price_created_timestamp_auto_set(self, session):
        """Test that created timestamp is auto-set upon insertion."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        before = datetime.now()
        price = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
        )
        session.add(price)
        session.commit()
        after = datetime.now()

        assert before <= price.created <= after

    # Composite primary key tests

    @pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")
    def test_price_duplicate_composite_key_violation(self, session):
        """Test that duplicate (security_key, date) raises IntegrityError."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        price1 = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
        )
        session.add(price1)
        session.commit()

        price2 = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("200.0000"),
            high=Decimal("200.0000"),
            low=Decimal("200.0000"),
            close=Decimal("200.0000"),
        )
        session.add(price2)

        with pytest.raises(IntegrityError, match="UNIQUE constraint failed"):
            session.commit()

    def test_price_same_security_different_dates_allowed(self, session):
        """Test that same security with different dates is allowed."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        price1 = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
        )
        price2 = Price(
            security_key=security.key,
            date=date(2024, 1, 16),
            open=Decimal("101.0000"),
            high=Decimal("101.0000"),
            low=Decimal("101.0000"),
            close=Decimal("101.0000"),
        )

        session.add(price1)
        session.add(price2)
        session.commit()

        retrieved1 = session.get(
            Price, {"security_key": "TEST", "date": date(2024, 1, 15)}
        )
        retrieved2 = session.get(
            Price, {"security_key": "TEST", "date": date(2024, 1, 16)}
        )
        assert retrieved1.close == Decimal("100.0000")
        assert retrieved2.close == Decimal("101.0000")

    def test_price_different_securities_same_date_allowed(self, session):
        """Test that different securities with same date are allowed."""
        security1 = Security(
            key="SEC1",
            name="Security 1",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        security2 = Security(
            key="SEC2",
            name="Security 2",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add_all([security1, security2])
        session.commit()

        price1 = Price(
            security_key=security1.key,
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
        )
        price2 = Price(
            security_key=security2.key,
            date=date(2024, 1, 15),
            open=Decimal("200.0000"),
            high=Decimal("200.0000"),
            low=Decimal("200.0000"),
            close=Decimal("200.0000"),
        )

        session.add(price1)
        session.add(price2)
        session.commit()

        retrieved1 = session.get(
            Price, {"security_key": "SEC1", "date": date(2024, 1, 15)}
        )
        retrieved2 = session.get(
            Price, {"security_key": "SEC2", "date": date(2024, 1, 15)}
        )
        assert retrieved1.close == Decimal("100.0000")
        assert retrieved2.close == Decimal("200.0000")

    # Foreign key constraint tests

    @pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")
    def test_price_invalid_security_key_fails(self, session):
        """Test that invalid security_key raises IntegrityError."""
        price = Price(
            security_key="NONEXISTENT",
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
        )
        session.add(price)

        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            session.commit()

    # Relationship tests

    def test_price_security_relationship(self, session):
        """Test that Price.security relationship loads correctly."""
        security = Security(
            key="RELI",
            name="Reliance Industries",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        price = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("2500.0000"),
            high=Decimal("2550.0000"),
            low=Decimal("2480.0000"),
            close=Decimal("2530.0000"),
        )
        session.add(price)
        session.commit()

        retrieved = session.get(
            Price, {"security_key": "RELI", "date": date(2024, 1, 15)}
        )
        assert retrieved.security is not None
        assert retrieved.security.name == "Reliance Industries"
        assert retrieved.security.key == "RELI"

    # Decimal precision persistence tests

    def test_price_ohlc_precision_persists(self, session):
        """Test that OHLC precision (24,4) is preserved."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        price = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("1234.5678"),
            high=Decimal("1235.9999"),
            low=Decimal("1233.0001"),
            close=Decimal("1234.1234"),
        )
        session.add(price)
        session.commit()
        price_id = {"security_key": security.key, "date": date(2024, 1, 15)}

        retrieved = session.get(Price, price_id)
        assert retrieved.open == Decimal("1234.5678")
        assert retrieved.high == Decimal("1235.9999")
        assert retrieved.low == Decimal("1233.0001")
        assert retrieved.close == Decimal("1234.1234")

    # JSON properties tests

    def test_price_properties_persist_as_json(self, session):
        """Test that properties are persisted and retrieved correctly as JSON."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        props = {"source": "AMFI", "provider": "mfapi.in"}
        price = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
            properties=props,
        )
        session.add(price)
        session.commit()
        price_id = {"security_key": security.key, "date": date(2024, 1, 15)}

        retrieved = session.get(Price, price_id)
        assert retrieved.properties == props

    def test_price_complex_properties_persist(self, session):
        """Test that complex properties persist correctly."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        props = {
            "market_data": {"volume": 1000000, "trades": 5000, "vwap": 103.25},
            "indicators": {"rsi": 65.5, "macd": 1.25},
            "tags": ["high-volume", "bullish"],
        }
        price = Price(
            security_key=security.key,
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("105.0000"),
            low=Decimal("99.0000"),
            close=Decimal("103.0000"),
            properties=props,
        )
        session.add(price)
        session.commit()
        price_id = {"security_key": security.key, "date": date(2024, 1, 15)}

        retrieved = session.get(Price, price_id)
        assert retrieved.properties["market_data"]["volume"] == 1000000
        assert retrieved.properties["indicators"]["rsi"] == 65.5
        assert "bullish" in retrieved.properties["tags"]

    # Multiple prices test

    def test_multiple_prices_same_security(self, session):
        """Test inserting multiple prices for same security (time series)."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.now(),
        )
        session.add(security)
        session.commit()

        prices = [
            Price(
                security_key=security.key,
                date=date(2024, 1, i),
                open=Decimal(f"{100 + i}.0000"),
                high=Decimal(f"{105 + i}.0000"),
                low=Decimal(f"{95 + i}.0000"),
                close=Decimal(f"{103 + i}.0000"),
            )
            for i in range(1, 6)
        ]
        session.add_all(prices)
        session.commit()

        # Verify all 5 prices are stored
        from sqlmodel import select

        retrieved_prices = session.exec(
            select(Price).where(Price.security_key == "TEST")
        ).all()
        assert len(retrieved_prices) == 5
        assert all(p.security_key == "TEST" for p in retrieved_prices)


class TestTransactionModels:
    """Pure model validation tests (no database)."""

    # Happy path tests

    def test_transaction_with_required_fields(self):
        """Test creating a Transaction with all required fields."""
        transaction = Transaction(
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

    def test_transaction_with_properties(self):
        """Test creating a Transaction with properties."""
        transaction = Transaction(
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

    # Enum validation tests

    def test_transaction_all_types_valid(self):
        """Test all TransactionType enum values are valid."""
        for txn_type in TransactionType:
            transaction = Transaction(
                transaction_date=date(2024, 1, 15),
                type=txn_type,
                description="Test",
                amount=Decimal("100.00"),
                units=Decimal("1.000"),
                security_key="TEST",
                account_id=1,
            )
            assert transaction.type == txn_type

    # Decimal precision tests

    def test_transaction_decimal_from_string(self):
        """Test creating Transaction with Decimal from string."""
        transaction = Transaction(
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

    def test_transaction_large_decimal_values(self):
        """Test Transaction with large Decimal values."""
        transaction = Transaction(
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
        """Test creating Transaction with empty properties dict."""
        transaction = Transaction(
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
        """Test creating Transaction with nested properties."""
        props = {
            "trade_details": {"broker": "Zerodha", "charges": 15.50},
            "tags": ["sip", "monthly"],
        }
        transaction = Transaction(
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
        """Test creating Transaction with unicode description."""
        transaction = Transaction(
            transaction_date=date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="म्यूचुअल फंड खरीदा",
            amount=Decimal("100.00"),
            units=Decimal("1.000"),
            security_key="TEST",
            account_id=1,
        )
        assert transaction.description == "म्यूचुअल फंड खरीदा"


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

        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
        assert account.id is not None

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
                account_id=account.id,  # ty:ignore[invalid-argument-type]
            )
            for i in range(1, 6)
        ]
        session.add_all(transactions)
        session.commit()

        retrieved_transactions = session.exec(select(Transaction)).all()
        assert len(retrieved_transactions) == 5
        assert all(t.security_key == "TEST" for t in retrieved_transactions)
        assert all(t.account_id == account.id for t in retrieved_transactions)

"""Tests for SQLite models."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from niveshpy.infrastructure.sqlite.models import Account, Security
from niveshpy.models.security import SecurityCategory, SecurityCreate, SecurityType


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

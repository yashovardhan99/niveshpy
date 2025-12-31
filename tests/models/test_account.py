"""Tests for all account models."""

from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from niveshpy.models.account import Account, AccountCreate


class TestAccountModels:
    """Tests for account models.

    These are pure model validation tests and do not interact with the database.
    """

    # Happy path tests

    def test_account_create_with_required_fields(self):
        """Test creating an AccountCreate instance with required fields only."""
        account = AccountCreate(name="HDFC Savings", institution="HDFC Bank")
        assert account.name == "HDFC Savings"
        assert account.institution == "HDFC Bank"
        assert account.properties == {}

    def test_account_create_with_properties(self):
        """Test creating an AccountCreate instance with properties."""
        account = AccountCreate(
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

    # Validation error tests

    def test_account_create_missing_name(self):
        """Test creating an AccountCreate instance missing the name field."""
        with pytest.raises(ValidationError, match="Field required"):
            AccountCreate(institution="ICICI")

    def test_account_create_missing_institution(self):
        """Test creating an AccountCreate instance missing the institution field."""
        with pytest.raises(ValidationError, match="Field required"):
            AccountCreate(name="Savings")

    def test_account_create_missing_both_fields(self):
        """Test creating an AccountCreate instance missing both required fields."""
        with pytest.raises(ValidationError):
            AccountCreate()

    def test_account_properties_none_raises_error(self):
        """Test that explicitly passing None for properties raises ValidationError."""
        with pytest.raises(ValidationError):
            AccountCreate(name="A", institution="B", properties=None)

    # Type validation tests

    def test_account_create_wrong_type_name(self):
        """Test creating an AccountCreate instance with wrong type for name."""
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            AccountCreate(name=12345, institution="Bank")

    def test_account_create_wrong_type_institution(self):
        """Test creating an AccountCreate instance with wrong type for institution."""
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            AccountCreate(name="Account", institution=None)

    def test_account_properties_must_be_dict(self):
        """Test creating an AccountCreate instance with wrong type for properties."""
        with pytest.raises(ValidationError, match="Input should be a valid dictionary"):
            AccountCreate(name="A", institution="B", properties="not_a_dict")

    # Edge cases

    def test_account_empty_properties_dict(self):
        """Test creating an AccountCreate instance with empty properties dict."""
        account = AccountCreate(name="A", institution="B", properties={})
        assert account.properties == {}

    def test_account_nested_properties(self):
        """Test creating an AccountCreate instance with nested properties."""
        props = {
            "details": {"type": "savings", "currency": "INR"},
            "tags": ["primary", "active"],
        }
        account = AccountCreate(name="A", institution="B", properties=props)
        assert account.properties["details"]["currency"] == "INR"
        assert "primary" in account.properties["tags"]

    def test_account_unicode_characters(self):
        """Test creating an AccountCreate instance with unicode characters."""
        account = AccountCreate(name="बचत खाता", institution="भारतीय स्टेट बैंक")
        assert account.name == "बचत खाता"

    def test_account_special_characters(self):
        """Test creating an AccountCreate instance with special characters."""
        account = AccountCreate(name="Account #1", institution="Bank & Co.")
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

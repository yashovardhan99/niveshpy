"""Tests for all security models."""

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from niveshpy.models.security import (
    Security,
    SecurityCategory,
    SecurityCreate,
    SecurityType,
)


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

    def test_security_invalid_type_string(self):
        """Test that invalid type string raises ValidationError."""
        with pytest.raises(ValidationError, match="input_value='INVALID_TYPE'"):
            SecurityCreate(
                key="TEST",
                name="Test",
                type="INVALID_TYPE",
                category=SecurityCategory.EQUITY,
            )

    def test_security_invalid_category_string(self):
        """Test that invalid category string raises ValidationError."""
        with pytest.raises(ValidationError, match="input_value='INVALID_CATEGORY'"):
            SecurityCreate(
                key="TEST",
                name="Test",
                type=SecurityType.STOCK,
                category="INVALID_CATEGORY",
            )

    # Required field validation tests

    def test_security_create_missing_key(self):
        """Test creating SecurityCreate without key raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            SecurityCreate(
                name="Test", type=SecurityType.STOCK, category=SecurityCategory.EQUITY
            )

    def test_security_create_missing_name(self):
        """Test creating SecurityCreate without name raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            SecurityCreate(
                key="TEST", type=SecurityType.STOCK, category=SecurityCategory.EQUITY
            )

    def test_security_create_missing_type(self):
        """Test creating SecurityCreate without type raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            SecurityCreate(
                key="TEST", name="Test Security", category=SecurityCategory.EQUITY
            )

    def test_security_create_missing_category(self):
        """Test creating SecurityCreate without category raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            SecurityCreate(key="TEST", name="Test Security", type=SecurityType.STOCK)

    # Type validation tests

    def test_security_wrong_type_key(self):
        """Test creating SecurityCreate with wrong type for key."""
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            SecurityCreate(
                key=123456,
                name="Test",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
            )

    def test_security_wrong_type_name(self):
        """Test creating SecurityCreate with wrong type for name."""
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            SecurityCreate(
                key="TEST",
                name=12345,
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
            )

    def test_security_properties_must_be_dict(self):
        """Test that properties must be a dict."""
        with pytest.raises(ValidationError, match="Input should be a valid dictionary"):
            SecurityCreate(
                key="TEST",
                name="Test",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
                properties="not_a_dict",
            )

    def test_security_properties_none_raises_error(self):
        """Test that explicitly passing None for properties raises ValidationError."""
        with pytest.raises(ValidationError, match="Input should be a valid dictionary"):
            SecurityCreate(
                key="TEST",
                name="Test",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
                properties=None,
            )

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

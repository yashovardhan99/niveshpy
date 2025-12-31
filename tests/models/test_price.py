"""Tests for all price models."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from niveshpy.models.price import Price, PriceCreate, PriceDisplay
from niveshpy.models.security import Security, SecurityCategory, SecurityType


class TestPriceModels:
    """Pure model validation tests (no database)."""

    # Happy path tests

    def test_price_create_with_required_fields(self):
        """Test creating a PriceCreate with all required fields."""
        price = PriceCreate(
            security_key="123456",
            date=date(2024, 1, 15),
            open=Decimal("100.5000"),
            high=Decimal("105.7500"),
            low=Decimal("99.2500"),
            close=Decimal("103.0000"),
        )
        assert price.security_key == "123456"
        assert price.date == date(2024, 1, 15)
        assert price.open == Decimal("100.5000")
        assert price.high == Decimal("105.7500")
        assert price.low == Decimal("99.2500")
        assert price.close == Decimal("103.0000")
        assert price.properties == {}

    def test_price_create_with_properties(self):
        """Test creating a PriceCreate with properties."""
        price = PriceCreate(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
            properties={"source": "NSE", "volume": 1000000},
        )
        assert price.properties["source"] == "NSE"
        assert price.properties["volume"] == 1000000

    def test_price_instance_creation(self):
        """Test creating a Price instance."""
        price = Price(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
        )
        assert price.security_key == "TEST"
        assert price.date == date(2024, 1, 15)

    # Required field validation tests

    def test_price_create_missing_security_key(self):
        """Test creating PriceCreate without security_key raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            PriceCreate(
                date=date(2024, 1, 15),
                open=Decimal("100.0000"),
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
            )

    def test_price_create_missing_date(self):
        """Test creating PriceCreate without date raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            PriceCreate(
                security_key="TEST",
                open=Decimal("100.0000"),
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
            )

    def test_price_create_missing_open(self):
        """Test creating PriceCreate without open raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            PriceCreate(
                security_key="TEST",
                date=date(2024, 1, 15),
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
            )

    def test_price_create_missing_high(self):
        """Test creating PriceCreate without high raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            PriceCreate(
                security_key="TEST",
                date=date(2024, 1, 15),
                open=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
            )

    def test_price_create_missing_low(self):
        """Test creating PriceCreate without low raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            PriceCreate(
                security_key="TEST",
                date=date(2024, 1, 15),
                open=Decimal("100.0000"),
                high=Decimal("100.0000"),
                close=Decimal("100.0000"),
            )

    def test_price_create_missing_close(self):
        """Test creating PriceCreate without close raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            PriceCreate(
                security_key="TEST",
                date=date(2024, 1, 15),
                open=Decimal("100.0000"),
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
            )

    # Type validation tests

    def test_price_wrong_type_security_key(self):
        """Test creating PriceCreate with wrong type for security_key."""
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            PriceCreate(
                security_key=123456,
                date=date(2024, 1, 15),
                open=Decimal("100.0000"),
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
            )

    def test_price_wrong_type_date(self):
        """Test creating PriceCreate with wrong type for date."""
        with pytest.raises(ValidationError, match="Input should be a valid date"):
            PriceCreate(
                security_key="TEST",
                date="not-a-date",
                open=Decimal("100.0000"),
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
            )

    def test_price_wrong_type_ohlc(self):
        """Test creating PriceCreate with wrong type for OHLC values."""
        with pytest.raises(ValidationError):
            PriceCreate(
                security_key="TEST",
                date=date(2024, 1, 15),
                open="not-a-number",
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
            )

    def test_price_properties_must_be_dict(self):
        """Test that properties must be a dict."""
        with pytest.raises(ValidationError, match="Input should be a valid dictionary"):
            PriceCreate(
                security_key="TEST",
                date=date(2024, 1, 15),
                open=Decimal("100.0000"),
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
                properties="not_a_dict",
            )

    # Decimal precision tests

    def test_price_decimal_from_string(self):
        """Test creating PriceCreate with Decimal from string."""
        price = PriceCreate(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("123.4567"),
            high=Decimal("125.9999"),
            low=Decimal("120.0001"),
            close=Decimal("124.5678"),
        )
        assert price.open == Decimal("123.4567")
        assert price.high == Decimal("125.9999")
        assert price.low == Decimal("120.0001")
        assert price.close == Decimal("124.5678")

    def test_price_decimal_from_float(self):
        """Test creating PriceCreate with Decimal from float (will convert)."""
        price = PriceCreate(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=100.5,
            high=105.75,
            low=99.25,
            close=103.0,
        )
        assert isinstance(price.open, Decimal)
        assert isinstance(price.high, Decimal)
        assert isinstance(price.low, Decimal)
        assert isinstance(price.close, Decimal)

    def test_price_four_decimal_precision(self):
        """Test PriceCreate with 4 decimal places (NUMERIC 24,4)."""
        price = PriceCreate(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("1234.5678"),
            high=Decimal("1234.5679"),
            low=Decimal("1234.5677"),
            close=Decimal("1234.5678"),
        )
        assert price.open == Decimal("1234.5678")

    def test_price_large_decimal_values(self):
        """Test PriceCreate with large Decimal values."""
        price = PriceCreate(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("99999999999999999999.9999"),
            high=Decimal("99999999999999999999.9999"),
            low=Decimal("99999999999999999999.9999"),
            close=Decimal("99999999999999999999.9999"),
        )
        assert price.open > 0

    # Edge cases

    def test_price_empty_properties_dict(self):
        """Test creating PriceCreate with empty properties dict."""
        price = PriceCreate(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
            properties={},
        )
        assert price.properties == {}

    def test_price_nested_properties(self):
        """Test creating PriceCreate with nested properties."""
        props = {
            "market_data": {"exchange": "NSE", "segment": "EQ"},
            "indicators": {"volume": 1000000, "trades": 5000},
        }
        price = PriceCreate(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
            properties=props,
        )
        assert price.properties["market_data"]["exchange"] == "NSE"
        assert price.properties["indicators"]["volume"] == 1000000

    def test_price_date_string_conversion(self):
        """Test that date strings are converted to date objects."""
        price = PriceCreate(
            security_key="TEST",
            date="2024-01-15",
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
        )
        assert price.date == date(2024, 1, 15)
        assert isinstance(price.date, date)

    def test_price_zero_values(self):
        """Test creating PriceCreate with zero OHLC values."""
        price = PriceCreate(
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("0.0000"),
            high=Decimal("0.0000"),
            low=Decimal("0.0000"),
            close=Decimal("0.0000"),
        )
        assert price.open == Decimal("0.0000")
        assert price.close == Decimal("0.0000")


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
        )
        security2 = Security(
            key="SEC2",
            name="Security 2",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
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


class TestPriceDisplay:
    """Tests for PriceDisplay model with field validator."""

    def test_price_display_security_validator_with_object(self):
        """Test that PriceDisplay formats Security object to string."""
        security = Security(
            key="TEST123",
            name="Test Mutual Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )

        price = PriceDisplay(
            security=security,  # Pass Security object
            security_key="TEST123",
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
            created=datetime.now(),
        )

        assert price.security == "Test Mutual Fund (TEST123)"

    def test_price_display_security_validator_with_string(self):
        """Test that PriceDisplay keeps string security as-is."""
        price = PriceDisplay(
            security="Already Formatted Security",
            security_key="TEST",
            date=date(2024, 1, 15),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
            created=datetime.now(),
        )

        assert price.security == "Already Formatted Security"

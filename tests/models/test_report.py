"""Tests for all report models."""

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from niveshpy.exceptions import OperationError
from niveshpy.models.account import Account
from niveshpy.models.report import (
    Allocation,
    AllocationBase,
    AllocationByCategory,
    AllocationByType,
    Holding,
    HoldingBase,
    HoldingDisplay,
    HoldingExport,
)
from niveshpy.models.security import Security, SecurityCategory, SecurityType


class TestHoldingBaseModel:
    """Tests for HoldingBase model."""

    # Happy path tests

    def test_holding_base_with_required_fields(self):
        """Test creating HoldingBase with all required fields."""
        holding = HoldingBase(
            date=datetime.date(2024, 1, 15),
            units=Decimal("100.50"),
            amount=Decimal("10500.75"),
        )
        assert holding.date == datetime.date(2024, 1, 15)
        assert holding.units == Decimal("100.50")
        assert holding.amount == Decimal("10500.75")

    def test_holding_base_with_zero_values(self):
        """Test creating HoldingBase with zero units and amount."""
        holding = HoldingBase(
            date=datetime.date(2024, 1, 15),
            units=Decimal("0"),
            amount=Decimal("0"),
        )
        assert holding.units == Decimal("0")
        assert holding.amount == Decimal("0")

    def test_holding_base_with_negative_values(self):
        """Test creating HoldingBase with negative units and amount."""
        holding = HoldingBase(
            date=datetime.date(2024, 1, 15),
            units=Decimal("-50.25"),
            amount=Decimal("-5000.00"),
        )
        assert holding.units == Decimal("-50.25")
        assert holding.amount == Decimal("-5000.00")

    # Field validation tests

    def test_holding_base_missing_date(self):
        """Test that missing date raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            HoldingBase(
                units=Decimal("100.50"),
                amount=Decimal("10500.75"),
            )

    def test_holding_base_missing_units(self):
        """Test that missing units raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            HoldingBase(
                date=datetime.date(2024, 1, 15),
                amount=Decimal("10500.75"),
            )

    def test_holding_base_missing_amount(self):
        """Test that missing amount raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            HoldingBase(
                date=datetime.date(2024, 1, 15),
                units=Decimal("100.50"),
            )

    # Type validation tests

    def test_holding_base_invalid_date_type(self):
        """Test that date string in ISO format is parsed to date."""
        # Pydantic v2 parses ISO format date strings
        holding = HoldingBase(
            date="2024-01-15",  # type: ignore[arg-type]  # Will be parsed to date
            units=Decimal("100.50"),
            amount=Decimal("10500.75"),
        )
        assert holding.date == datetime.date(2024, 1, 15)
        assert isinstance(holding.date, datetime.date)

    def test_holding_base_invalid_units_type(self):
        """Test that invalid units type is coerced or raises ValidationError."""
        # Pydantic may coerce strings to Decimal
        holding = HoldingBase(
            date=datetime.date(2024, 1, 15),
            units="100.50",  # type: ignore[arg-type]
            amount=Decimal("10500.75"),
        )
        assert holding.units == Decimal("100.50")

    def test_holding_base_invalid_amount_type(self):
        """Test that invalid amount type is coerced or raises ValidationError."""
        holding = HoldingBase(
            date=datetime.date(2024, 1, 15),
            units=Decimal("100.50"),
            amount="10500.75",  # type: ignore[arg-type]
        )
        assert holding.amount == Decimal("10500.75")


class TestHoldingModel:
    """Tests for Holding model."""

    # Happy path tests

    def test_holding_with_required_fields(self):
        """Test creating Holding with all required fields."""
        account = Account(name="Test Account", institution="Test Bank")
        security = Security(
            key="TEST123",
            name="Test Security",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 1, 15),
            units=Decimal("100.50"),
            amount=Decimal("10500.75"),
        )
        assert holding.account == account
        assert holding.security == security
        assert holding.date == datetime.date(2024, 1, 15)
        assert holding.units == Decimal("100.50")
        assert holding.amount == Decimal("10500.75")

    def test_holding_account_relationship(self):
        """Test that Holding correctly holds Account reference."""
        account = Account(id=1, name="Savings", institution="Bank")
        security = Security(
            key="SEC001",
            name="Security",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 1, 15),
            units=Decimal("10"),
            amount=Decimal("1000"),
        )
        assert holding.account.id == 1
        assert holding.account.name == "Savings"

    def test_holding_security_relationship(self):
        """Test that Holding correctly holds Security reference."""
        account = Account(name="Account", institution="Bank")
        security = Security(
            key="MF123",
            name="Mutual Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.DEBT,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 1, 15),
            units=Decimal("50"),
            amount=Decimal("5000"),
        )
        assert holding.security.key == "MF123"
        assert holding.security.type == SecurityType.MUTUAL_FUND

    # Field validation tests

    def test_holding_missing_account(self):
        """Test that missing account raises ValidationError."""
        security = Security(
            key="TEST",
            name="Test",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        with pytest.raises(ValidationError, match="Field required"):
            Holding(
                security=security,
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )

    def test_holding_missing_security(self):
        """Test that missing security raises ValidationError."""
        account = Account(name="Account", institution="Bank")
        with pytest.raises(ValidationError, match="Field required"):
            Holding(
                account=account,
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )


class TestHoldingDisplayModel:
    """Tests for HoldingDisplay model."""

    # Happy path tests

    def test_holding_display_creation(self):
        """Test creating HoldingDisplay with all fields."""
        display = HoldingDisplay(
            account="Test Account (Test Bank)",
            security="Test Security (TEST123)",
            date=datetime.date(2024, 1, 15),
            units=Decimal("100.50"),
            amount=Decimal("10500.75"),
        )
        assert display.account == "Test Account (Test Bank)"
        assert display.security == "Test Security (TEST123)"
        assert display.date == datetime.date(2024, 1, 15)
        assert display.units == Decimal("100.50")
        assert display.amount == Decimal("10500.75")

    def test_holding_display_from_holding(self):
        """Test creating HoldingDisplay from Holding using from_holding method."""
        account = Account(name="Savings Account", institution="HDFC Bank")
        security = Security(
            key="120503",
            name="HDFC Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 1, 15),
            units=Decimal("100.50"),
            amount=Decimal("10500.75"),
        )

        display = HoldingDisplay.from_holding(holding)

        assert display.account == "Savings Account (HDFC Bank)"
        assert display.security == "HDFC Equity Fund (120503)"
        assert display.date == datetime.date(2024, 1, 15)
        assert display.units == Decimal("100.50")
        assert display.amount == Decimal("10500.75")

    def test_holding_display_from_holding_preserves_data(self):
        """Test that from_holding preserves all numeric and date data."""
        account = Account(name="Investment", institution="Zerodha")
        security = Security(
            key="AAPL",
            name="Apple Inc",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 12, 31),
            units=Decimal("25.75"),
            amount=Decimal("5000.50"),
        )

        display = HoldingDisplay.from_holding(holding)

        # Verify exact values are preserved
        assert display.date == holding.date
        assert display.units == holding.units
        assert display.amount == holding.amount

    # Field validation tests

    def test_holding_display_missing_account(self):
        """Test that missing account raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            HoldingDisplay(
                security="Test Security (TEST)",
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )

    def test_holding_display_missing_security(self):
        """Test that missing security raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            HoldingDisplay(
                account="Test Account (Bank)",
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )

    # Type validation tests

    def test_holding_display_account_must_be_string(self):
        """Test that account field must be a string."""
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            HoldingDisplay(
                account=123,  # type: ignore[arg-type]  # Invalid type
                security="Security (SEC)",
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )

    def test_holding_display_security_must_be_string(self):
        """Test that security field must be a string."""
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            HoldingDisplay(
                account="Account (Bank)",
                security=456,  # type: ignore[arg-type]  # Invalid type
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )


class TestHoldingExportModel:
    """Tests for HoldingExport model."""

    # Happy path tests

    def test_holding_export_creation(self):
        """Test creating HoldingExport with all fields."""
        export = HoldingExport(
            account=1,
            security="TEST123",
            date=datetime.date(2024, 1, 15),
            units=Decimal("100.50"),
            amount=Decimal("10500.75"),
        )
        assert export.account == 1
        assert export.security == "TEST123"
        assert export.date == datetime.date(2024, 1, 15)
        assert export.units == Decimal("100.50")
        assert export.amount == Decimal("10500.75")

    def test_holding_export_from_holding_with_account_id(self):
        """Test creating HoldingExport from Holding with account ID."""
        account = Account(id=42, name="Savings", institution="HDFC")
        security = Security(
            key="120503",
            name="HDFC Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 1, 15),
            units=Decimal("100.50"),
            amount=Decimal("10500.75"),
        )

        export = HoldingExport.from_holding(holding)

        assert export.account == 42
        assert export.security == "120503"
        assert export.date == datetime.date(2024, 1, 15)
        assert export.units == Decimal("100.50")
        assert export.amount == Decimal("10500.75")

    def test_holding_export_from_holding_without_account_id(self):
        """Test that from_holding raises OperationError when account ID is None."""
        account = Account(id=None, name="Savings", institution="HDFC")
        security = Security(
            key="TEST",
            name="Test Security",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        holding = Holding(
            account=account,
            security=security,
            date=datetime.date(2024, 1, 15),
            units=Decimal("100"),
            amount=Decimal("1000"),
        )

        with pytest.raises(OperationError, match="Account ID is required for export"):
            HoldingExport.from_holding(holding)

    # Field validation tests

    def test_holding_export_missing_account(self):
        """Test that missing account raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            HoldingExport(  # type: ignore[call-arg]
                security="TEST",
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )

    def test_holding_export_missing_security(self):
        """Test that missing security raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            HoldingExport(  # type: ignore[call-arg]
                account=1,
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )

    # Type validation tests

    def test_holding_export_account_must_be_int(self):
        """Test that account field must be an integer."""
        # Pydantic may coerce string to int
        export = HoldingExport(
            account="1",  # type: ignore[arg-type]
            security="TEST",
            date=datetime.date(2024, 1, 15),
            units=Decimal("100"),
            amount=Decimal("1000"),
        )
        assert export.account == 1
        assert isinstance(export.account, int)

    def test_holding_export_security_must_be_string(self):
        """Test that security field must be a string and does not coerce int."""
        # Pydantic v2 does NOT coerce int to string for this field
        with pytest.raises(ValidationError, match="Input should be a valid string"):
            HoldingExport(
                account=1,
                security=123456,  # type: ignore[arg-type]
                date=datetime.date(2024, 1, 15),
                units=Decimal("100"),
                amount=Decimal("1000"),
            )


class TestAllocationBaseModel:
    """Tests for AllocationBase model."""

    # Happy path tests

    def test_allocation_base_with_required_fields(self):
        """Test creating AllocationBase with all required fields."""
        allocation = AllocationBase(
            date=datetime.date(2024, 1, 15),
            amount=Decimal("10500.75"),
            allocation=Decimal("0.3500"),
        )
        assert allocation.date == datetime.date(2024, 1, 15)
        assert allocation.amount == Decimal("10500.75")
        assert allocation.allocation == Decimal("0.3500")

    def test_allocation_base_with_zero_values(self):
        """Test creating AllocationBase with zero amount and allocation."""
        allocation = AllocationBase(
            date=datetime.date(2024, 1, 15),
            amount=Decimal("0"),
            allocation=Decimal("0"),
        )
        assert allocation.amount == Decimal("0")
        assert allocation.allocation == Decimal("0")

    def test_allocation_base_with_full_allocation(self):
        """Test creating AllocationBase with 100% allocation."""
        allocation = AllocationBase(
            date=datetime.date(2024, 1, 15),
            amount=Decimal("50000.00"),
            allocation=Decimal("1.0000"),
        )
        assert allocation.allocation == Decimal("1.0000")

    # Field validation tests

    def test_allocation_base_missing_date(self):
        """Test that missing date raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            AllocationBase(
                amount=Decimal("10500.75"),
                allocation=Decimal("0.3500"),
            )

    def test_allocation_base_missing_amount(self):
        """Test that missing amount raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            AllocationBase(
                date=datetime.date(2024, 1, 15),
                allocation=Decimal("0.3500"),
            )

    def test_allocation_base_missing_allocation(self):
        """Test that missing allocation raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            AllocationBase(
                date=datetime.date(2024, 1, 15),
                amount=Decimal("10500.75"),
            )

    # Type validation tests

    def test_allocation_base_date_string_parsed(self):
        """Test that date string in ISO format is parsed to date."""
        allocation = AllocationBase(
            date="2024-01-15",  # type: ignore[arg-type]
            amount=Decimal("10500.75"),
            allocation=Decimal("0.3500"),
        )
        assert allocation.date == datetime.date(2024, 1, 15)

    def test_allocation_base_amount_string_coerced(self):
        """Test that amount string is coerced to Decimal."""
        allocation = AllocationBase(
            date=datetime.date(2024, 1, 15),
            amount="10500.75",  # type: ignore[arg-type]
            allocation=Decimal("0.3500"),
        )
        assert allocation.amount == Decimal("10500.75")


class TestAllocationByTypeModel:
    """Tests for AllocationByType model."""

    # Happy path tests

    def test_allocation_by_type_with_required_fields(self):
        """Test creating AllocationByType with all required fields."""
        allocation = AllocationByType(
            security_type=SecurityType.MUTUAL_FUND,
            date=datetime.date(2024, 1, 15),
            amount=Decimal("10500.75"),
            allocation=Decimal("0.3500"),
        )
        assert allocation.security_type == SecurityType.MUTUAL_FUND
        assert allocation.date == datetime.date(2024, 1, 15)
        assert allocation.amount == Decimal("10500.75")
        assert allocation.allocation == Decimal("0.3500")

    def test_allocation_by_type_all_security_types(self):
        """Test creating AllocationByType with all security types."""
        for sec_type in SecurityType:
            allocation = AllocationByType(
                security_type=sec_type,
                date=datetime.date(2024, 1, 15),
                amount=Decimal("1000.00"),
                allocation=Decimal("0.2000"),
            )
            assert allocation.security_type == sec_type

    # Field validation tests

    def test_allocation_by_type_missing_security_type(self):
        """Test that missing security_type raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            AllocationByType(
                date=datetime.date(2024, 1, 15),
                amount=Decimal("10500.75"),
                allocation=Decimal("0.3500"),
            )

    # Type validation tests

    def test_allocation_by_type_invalid_security_type(self):
        """Test that invalid security type raises ValidationError."""
        with pytest.raises(ValidationError):
            AllocationByType(
                security_type="invalid_type",  # type: ignore[arg-type]
                date=datetime.date(2024, 1, 15),
                amount=Decimal("10500.75"),
                allocation=Decimal("0.3500"),
            )


class TestAllocationByCategoryModel:
    """Tests for AllocationByCategory model."""

    # Happy path tests

    def test_allocation_by_category_with_required_fields(self):
        """Test creating AllocationByCategory with all required fields."""
        allocation = AllocationByCategory(
            security_category=SecurityCategory.EQUITY,
            date=datetime.date(2024, 1, 15),
            amount=Decimal("10500.75"),
            allocation=Decimal("0.3500"),
        )
        assert allocation.security_category == SecurityCategory.EQUITY
        assert allocation.date == datetime.date(2024, 1, 15)
        assert allocation.amount == Decimal("10500.75")
        assert allocation.allocation == Decimal("0.3500")

    def test_allocation_by_category_all_categories(self):
        """Test creating AllocationByCategory with all security categories."""
        for category in SecurityCategory:
            allocation = AllocationByCategory(
                security_category=category,
                date=datetime.date(2024, 1, 15),
                amount=Decimal("1000.00"),
                allocation=Decimal("0.2000"),
            )
            assert allocation.security_category == category

    # Field validation tests

    def test_allocation_by_category_missing_security_category(self):
        """Test that missing security_category raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            AllocationByCategory(
                date=datetime.date(2024, 1, 15),
                amount=Decimal("10500.75"),
                allocation=Decimal("0.3500"),
            )

    # Type validation tests

    def test_allocation_by_category_invalid_category(self):
        """Test that invalid security category raises ValidationError."""
        with pytest.raises(ValidationError):
            AllocationByCategory(
                security_category="invalid_category",  # type: ignore[arg-type]
                date=datetime.date(2024, 1, 15),
                amount=Decimal("10500.75"),
                allocation=Decimal("0.3500"),
            )


class TestAllocationModel:
    """Tests for Allocation model."""

    # Happy path tests

    def test_allocation_with_required_fields(self):
        """Test creating Allocation with all required fields."""
        allocation = Allocation(
            security_type=SecurityType.MUTUAL_FUND,
            security_category=SecurityCategory.EQUITY,
            date=datetime.date(2024, 1, 15),
            amount=Decimal("10500.75"),
            allocation=Decimal("0.3500"),
        )
        assert allocation.security_type == SecurityType.MUTUAL_FUND
        assert allocation.security_category == SecurityCategory.EQUITY
        assert allocation.date == datetime.date(2024, 1, 15)
        assert allocation.amount == Decimal("10500.75")
        assert allocation.allocation == Decimal("0.3500")

    def test_allocation_all_combinations(self):
        """Test creating Allocation with various type/category combinations."""
        # Test a few common combinations
        combos = [
            (SecurityType.MUTUAL_FUND, SecurityCategory.EQUITY),
            (SecurityType.MUTUAL_FUND, SecurityCategory.DEBT),
            (SecurityType.STOCK, SecurityCategory.EQUITY),
            (SecurityType.BOND, SecurityCategory.DEBT),
        ]
        for sec_type, sec_category in combos:
            allocation = Allocation(
                security_type=sec_type,
                security_category=sec_category,
                date=datetime.date(2024, 1, 15),
                amount=Decimal("1000.00"),
                allocation=Decimal("0.2000"),
            )
            assert allocation.security_type == sec_type
            assert allocation.security_category == sec_category

    # Field validation tests

    def test_allocation_missing_security_type(self):
        """Test that missing security_type raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            Allocation(
                security_category=SecurityCategory.EQUITY,
                date=datetime.date(2024, 1, 15),
                amount=Decimal("10500.75"),
                allocation=Decimal("0.3500"),
            )

    def test_allocation_missing_security_category(self):
        """Test that missing security_category raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            Allocation(
                security_type=SecurityType.MUTUAL_FUND,
                date=datetime.date(2024, 1, 15),
                amount=Decimal("10500.75"),
                allocation=Decimal("0.3500"),
            )

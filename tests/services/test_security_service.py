"""Tests for SecurityService."""

from collections.abc import Sequence
from unittest.mock import patch

import pytest

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.exceptions import AmbiguousResourceError, InvalidInputError
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.services.security import SecurityService
from tests.services.conftest import MockSecurityRepository


@pytest.fixture
def security_service() -> SecurityService:
    """Create SecurityService instance with mock repository."""
    return SecurityService(security_repository=MockSecurityRepository())


@pytest.fixture
def sample_securities(security_service):
    """Create sample securities for testing."""
    securities = [
        Security(
            key="123456",
            name="HDFC Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        ),
        Security(
            key="234567",
            name="ICICI Liquid Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.DEBT,
        ),
        Security(
            key="RELI",
            name="Reliance Industries",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        ),
        Security(
            key="NIFTY",
            name="Nifty 50 ETF",
            type=SecurityType.ETF,
            category=SecurityCategory.EQUITY,
        ),
        Security(
            key="GOLD",
            name="Gold Bond",
            type=SecurityType.BOND,
            category=SecurityCategory.COMMODITY,
        ),
    ]
    security_service.security_repository.insert_multiple_securities(securities)
    return securities


class TestListSecurities:
    """Tests for list_securities method."""

    def test_list_all_securities_no_filter(self, security_service, sample_securities):
        """Test listing all securities without any filters."""
        securities = security_service.list_securities(queries=(), limit=30, offset=0)

        assert len(securities) == 5
        assert all(isinstance(sec, Security) for sec in securities)
        assert securities[0].key == "123456"

    def test_list_securities_with_limit(self, security_service, sample_securities):
        """Test listing securities with limit."""
        securities = security_service.list_securities(queries=(), limit=3, offset=0)

        assert len(securities) == 3

    def test_list_securities_with_offset(self, security_service, sample_securities):
        """Test listing securities with offset."""
        securities = security_service.list_securities(queries=(), limit=30, offset=2)

        assert len(securities) == 3
        assert securities[0].key == "GOLD"

    def test_list_securities_with_limit_and_offset(
        self, security_service, sample_securities
    ):
        """Test listing securities with both limit and offset."""
        securities = security_service.list_securities(queries=(), limit=2, offset=1)

        assert len(securities) == 2
        assert securities[0].key == "234567"

    def test_list_securities_offset_beyond_total(
        self, security_service, sample_securities
    ):
        """Test listing securities with offset beyond total count."""
        securities = security_service.list_securities(queries=(), limit=30, offset=10)

        assert len(securities) == 0

    def test_list_securities_with_query_filter(
        self, security_service, sample_securities
    ):
        """Test listing securities with query filter."""
        with patch.object(
            security_service.security_repository,
            "find_securities",
            return_value=[sample_securities[0]],
        ) as mock:
            securities = security_service.list_securities(
                queries=("HDFC",), limit=30, offset=0
            )
            mock.assert_called_once()
            mock.assert_called_with(
                [FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "HDFC")],
                limit=30,
                offset=0,
            )

        assert len(securities) == 1
        assert "HDFC" in securities[0].name

    def test_list_securities_empty_database(self, security_service):
        """Test listing securities when database is empty."""
        securities = security_service.list_securities(queries=(), limit=30, offset=0)

        assert len(securities) == 0

    def test_list_securities_invalid_limit_zero(
        self, security_service, sample_securities
    ):
        """Test that zero limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be positive"):
            security_service.list_securities(queries=(), limit=0, offset=0)

    def test_list_securities_invalid_limit_negative(
        self, security_service, sample_securities
    ):
        """Test that negative limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be positive"):
            security_service.list_securities(queries=(), limit=-1, offset=0)

    def test_list_securities_invalid_offset_negative(
        self, security_service, sample_securities
    ):
        """Test that negative offset raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Offset cannot be negative"):
            security_service.list_securities(queries=(), limit=30, offset=-1)


class TestAddSecurity:
    """Tests for add_security method."""

    def test_add_security_success(self, security_service):
        """Test successfully adding a new security."""
        result = security_service.add_security(
            key="TEST123",
            name="Test Mutual Fund",
            stype=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            source=None,
        )

        assert result is True

    def test_add_security_with_source(self, security_service):
        """Test adding security with source property."""
        result = security_service.add_security(
            key="TEST123",
            name="Test Fund",
            stype=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            source="AMFI",
        )

        assert result is True

    def test_add_security_duplicate_key_ignored(
        self, security_service: SecurityService
    ):
        """Test that adding a security with duplicate key updates existing one."""
        # Add first security
        result1 = security_service.add_security(
            key="DUP123",
            name="Original Name",
            stype=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            source=None,
        )

        assert result1 is True

        # Add with same key but different details
        result2 = security_service.add_security(
            key="DUP123",
            name="Updated Name",
            stype=SecurityType.STOCK,
            category=SecurityCategory.DEBT,
            source="Manual",
        )

        assert result2 is False
        # Verify original security is unchanged
        securities = security_service.list_securities(queries=(), limit=30, offset=0)
        for sec in securities:
            if sec.key == "DUP123":
                assert sec.name == "Original Name"
                assert sec.type == SecurityType.MUTUAL_FUND
                assert sec.category == SecurityCategory.EQUITY
                assert sec.properties.get("source") is None
                break
        else:
            pytest.fail(
                "Security with key 'DUP123' not found after duplicate add attempt."
            )

    def test_add_security_strips_whitespace(self, security_service):
        """Test that add_security strips whitespace from key and name."""
        result = security_service.add_security(
            key="  TEST123  ",
            name="  Test Fund  ",
            stype=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            source=None,
        )

        assert result is True
        securities = security_service.list_securities(queries=(), limit=30, offset=0)
        for sec in securities:
            if sec.key == "TEST123":
                assert sec.name == "Test Fund"
                break
        else:
            pytest.fail("Security with key 'TEST123' not found after add attempt.")

    def test_add_security_empty_key_raises_error(self, security_service):
        """Test that empty key raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Security key and name cannot be empty"
        ):
            security_service.add_security(
                key="",
                name="Test",
                stype=SecurityType.MUTUAL_FUND,
                category=SecurityCategory.EQUITY,
                source=None,
            )

    def test_add_security_whitespace_only_key_raises_error(self, security_service):
        """Test that whitespace-only key raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Security key and name cannot be empty"
        ):
            security_service.add_security(
                key="   ",
                name="Test",
                stype=SecurityType.MUTUAL_FUND,
                category=SecurityCategory.EQUITY,
                source=None,
            )

    def test_add_security_empty_name_raises_error(self, security_service):
        """Test that empty name raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Security key and name cannot be empty"
        ):
            security_service.add_security(
                key="TEST",
                name="",
                stype=SecurityType.MUTUAL_FUND,
                category=SecurityCategory.EQUITY,
                source=None,
            )

    def test_add_security_whitespace_only_name_raises_error(self, security_service):
        """Test that whitespace-only name raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Security key and name cannot be empty"
        ):
            security_service.add_security(
                key="TEST",
                name="   ",
                stype=SecurityType.MUTUAL_FUND,
                category=SecurityCategory.EQUITY,
                source=None,
            )

    def test_add_security_invalid_type_raises_error(self, security_service):
        """Test that invalid security type raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Invalid security type"):
            security_service.add_security(
                key="TEST",
                name="Test",
                stype="INVALID_TYPE",
                category=SecurityCategory.EQUITY,
                source=None,
            )

    def test_add_security_invalid_category_raises_error(self, security_service):
        """Test that invalid security category raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Invalid security category"):
            security_service.add_security(
                key="TEST",
                name="Test",
                stype=SecurityType.MUTUAL_FUND,
                category="INVALID_CATEGORY",
                source=None,
            )

    def test_add_security_all_types_valid(self, security_service):
        """Test adding securities with all valid SecurityType values."""
        for idx, sec_type in enumerate(SecurityType):
            result = security_service.add_security(
                key=f"TYPE{idx}",
                name=f"Test {sec_type.value}",
                stype=sec_type,
                category=SecurityCategory.OTHER,
                source=None,
            )
            assert result is True

    def test_add_security_all_categories_valid(self, security_service):
        """Test adding securities with all valid SecurityCategory values."""
        for idx, category in enumerate(SecurityCategory):
            result = security_service.add_security(
                key=f"CAT{idx}",
                name=f"Test {category.value}",
                stype=SecurityType.OTHER,
                category=category,
                source=None,
            )
            assert result is True

    def test_add_security_special_characters(self, security_service):
        """Test adding security with special characters."""
        result = security_service.add_security(
            key="SP&500",
            name="S&P 500 (Growth)",
            stype=SecurityType.ETF,
            category=SecurityCategory.EQUITY,
            source=None,
        )

        assert result is True

    def test_add_security_unicode_characters(self, security_service):
        """Test adding security with unicode characters."""
        result = security_service.add_security(
            key="123456",
            name="भारतीय म्यूचुअल फंड",
            stype=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            source=None,
        )

        assert result is True


class TestResolveSecurityKey:
    """Tests for resolve_security_key method."""

    def test_resolve_empty_queries_ambiguous_allowed(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test resolving with empty queries when ambiguous is allowed."""
        securities: Sequence[Security] = security_service.resolve_security_key(
            queries=(), limit=10, allow_ambiguous=True
        )

        assert len(securities) == 5

    def test_resolve_empty_queries_ambiguous_not_allowed(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test resolving with empty queries when ambiguous is not allowed."""
        with pytest.raises(InvalidInputError, match="No queries provided"):
            security_service.resolve_security_key(
                queries=(), limit=10, allow_ambiguous=False
            )

    def test_resolve_empty_queries_respects_limit(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test that empty queries resolution respects limit."""
        securities: Sequence[Security] = security_service.resolve_security_key(
            queries=(), limit=3, allow_ambiguous=True
        )

        assert len(securities) == 3

    def test_resolve_exact_match_by_key(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test resolving by exact security key."""
        securities: Sequence[Security] = security_service.resolve_security_key(
            queries=("123456",), limit=10, allow_ambiguous=True
        )

        assert len(securities) == 1
        assert securities[0].key == "123456"
        assert securities[0].name == "HDFC Equity Fund"

    def test_resolve_exact_match_by_key_with_whitespace(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test resolving by key with surrounding whitespace."""
        securities: Sequence[Security] = security_service.resolve_security_key(
            queries=("  RELI  ",), limit=10, allow_ambiguous=True
        )

        assert len(securities) == 1
        assert securities[0].key == "RELI"

    def test_resolve_nonexistent_key_ambiguous_not_allowed(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test resolving non-existent key when ambiguous not allowed."""
        with pytest.raises(AmbiguousResourceError, match="security"):
            security_service.resolve_security_key(
                queries=("NONEXIST",), limit=10, allow_ambiguous=False
            )

    def test_resolve_nonexistent_key_ambiguous_allowed(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test resolving non-existent key when ambiguous allowed falls back to text search."""
        with patch.object(
            security_service.security_repository,
            "find_securities",
            return_value=[],
        ) as mock:
            securities: Sequence[Security] = security_service.resolve_security_key(
                queries=("NONEXIST",), limit=10, allow_ambiguous=True
            )
            mock.assert_called_once()
            mock.assert_called_with(
                [FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "NONEXIST")],
                limit=10,
                offset=0,
            )

        assert len(securities) == 0

    def test_resolve_text_search_single_match(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test text search with exactly one match."""
        with patch.object(
            security_service.security_repository,
            "find_securities",
            return_value=[sample_securities[2]],
        ) as mock:
            securities: Sequence[Security] = security_service.resolve_security_key(
                queries=("Reliance",), limit=10, allow_ambiguous=True
            )
            mock.assert_called_once()
            mock.assert_called_with(
                [FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "Reliance")],
                limit=10,
                offset=0,
            )

        assert len(securities) == 1
        assert securities[0].name == "Reliance Industries"

    def test_resolve_text_search_multiple_matches_ambiguous_not_allowed(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test text search with multiple matches when ambiguous not allowed."""
        with pytest.raises(AmbiguousResourceError, match="security"):
            security_service.resolve_security_key(
                queries=("Fund",), limit=10, allow_ambiguous=False
            )

    def test_resolve_returns_security(
        self, security_service: SecurityService, sample_securities: list[Security]
    ):
        """Test that resolution returns Security instances."""
        securities: Sequence[Security] = security_service.resolve_security_key(
            queries=("123456",), limit=10, allow_ambiguous=True
        )

        assert isinstance(securities[0], Security)
        assert hasattr(securities[0], "key")
        assert hasattr(securities[0], "created")


class TestDeleteSecurity:
    """Tests for delete_security method."""

    def test_delete_security_success(self, security_service, sample_securities):
        """Test successfully deleting a security."""
        security_key = sample_securities[0].key
        result = security_service.delete_security(security_key)

        assert result is True

        # Verify security is deleted
        securities = security_service.list_securities(queries=(), limit=30, offset=0)
        assert len(securities) == 4
        assert not any(sec.key == security_key for sec in securities)

    def test_delete_security_nonexistent(self, security_service, sample_securities):
        """Test deleting non-existent security returns False."""
        result = security_service.delete_security("NONEXIST")

        assert result is False

    def test_delete_security_twice(self, security_service, sample_securities):
        """Test deleting same security twice."""
        security_key = sample_securities[0].key

        # First deletion should succeed
        result1 = security_service.delete_security(security_key)
        assert result1 is True

        # Second deletion should fail
        result2 = security_service.delete_security(security_key)
        assert result2 is False

    def test_delete_all_securities(self, security_service, sample_securities):
        """Test deleting all securities."""
        for security in sample_securities:
            result = security_service.delete_security(security.key)
            assert result is True

        # Verify all deleted
        securities = security_service.list_securities(queries=(), limit=30, offset=0)
        assert len(securities) == 0

    def test_delete_security_does_not_affect_others(
        self, security_service, sample_securities
    ):
        """Test that deleting one security doesn't affect others."""
        security_to_delete = sample_securities[2]
        initial_count = len(sample_securities)

        result = security_service.delete_security(security_to_delete.key)
        assert result is True

        # Verify only one security deleted
        remaining_securities = security_service.list_securities(
            queries=(), limit=30, offset=0
        )
        assert len(remaining_securities) == initial_count - 1
        assert not any(
            sec.key == security_to_delete.key for sec in remaining_securities
        )

"""Unit tests for query_filters.py functions.

Tests the pure-Python transformation of FilterNode/Col inputs into
Condition/Query outputs without requiring database or fixtures.
"""

from datetime import date
from decimal import Decimal

import pytest

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.exceptions import OperationError, QuerySyntaxError
from niveshpy.infrastructure.sqlite.query import Col
from niveshpy.infrastructure.sqlite.query_filters import (
    generate_query_from_filters,
    prepare_expression,
)

# ============================================================================
# Module-level helpers and constants
# ============================================================================


def _fn(field: Field, operator: Operator, value) -> FilterNode:
    """Shorthand for FilterNode construction."""
    return FilterNode(field=field, operator=operator, value=value)


# Column constants for testing
NAME_COL = Col("name")
AMOUNT_COL = Col("amount")
DATE_COL = Col("date")


# ============================================================================
# Phase 1: TestPrepareExpression (18 tests)
# ============================================================================


class TestPrepareExpression:
    """Tests for prepare_expression function."""

    # --- Happy path: one test per operator ---

    def test_regex_match(self):
        """Test REGEX_MATCH operator generates IREGEXP condition."""
        result = prepare_expression(
            _fn(Field.DESCRIPTION, Operator.REGEX_MATCH, "foo"), NAME_COL
        )
        assert "IREGEXP" in result.expression
        assert result.params == ("foo",)

    def test_not_regex_match(self):
        """Test NOT_REGEX_MATCH operator generates negated IREGEXP condition."""
        result = prepare_expression(
            _fn(Field.DESCRIPTION, Operator.NOT_REGEX_MATCH, "bar"), NAME_COL
        )
        assert "NOT" in result.expression
        assert "IREGEXP" in result.expression
        assert result.params == ("bar",)

    def test_equals_string(self):
        """Test EQUALS operator with string value."""
        result = prepare_expression(
            _fn(Field.SECURITY, Operator.EQUALS, "acme"), NAME_COL
        )
        assert "= ?" in result.expression
        assert result.params == ("acme",)

    def test_equals_decimal(self):
        """Test EQUALS operator with Decimal value."""
        value = Decimal("1.5")
        result = prepare_expression(
            _fn(Field.AMOUNT, Operator.EQUALS, value), AMOUNT_COL
        )
        assert "= ?" in result.expression
        assert result.params == (value,)

    def test_equals_date(self):
        """Test EQUALS operator with date value."""
        value = date(2024, 1, 1)
        result = prepare_expression(_fn(Field.DATE, Operator.EQUALS, value), DATE_COL)
        assert "= ?" in result.expression
        assert result.params == (value,)

    def test_not_equals(self):
        """Test NOT_EQUALS operator."""
        result = prepare_expression(
            _fn(Field.SECURITY, Operator.NOT_EQUALS, "x"), NAME_COL
        )
        assert "!= ?" in result.expression
        assert result.params == ("x",)

    def test_greater_than(self):
        """Test GREATER_THAN operator."""
        value = Decimal("100")
        result = prepare_expression(
            _fn(Field.AMOUNT, Operator.GREATER_THAN, value), AMOUNT_COL
        )
        assert "> ?" in result.expression
        assert result.params == (value,)

    def test_greater_than_eq(self):
        """Test GREATER_THAN_EQ operator."""
        value = Decimal("100")
        result = prepare_expression(
            _fn(Field.AMOUNT, Operator.GREATER_THAN_EQ, value), AMOUNT_COL
        )
        assert ">= ?" in result.expression
        assert result.params == (value,)

    def test_less_than(self):
        """Test LESS_THAN operator."""
        value = Decimal("50")
        result = prepare_expression(
            _fn(Field.AMOUNT, Operator.LESS_THAN, value), AMOUNT_COL
        )
        assert "< ?" in result.expression
        assert result.params == (value,)

    def test_less_than_eq(self):
        """Test LESS_THAN_EQ operator."""
        value = Decimal("50")
        result = prepare_expression(
            _fn(Field.AMOUNT, Operator.LESS_THAN_EQ, value), AMOUNT_COL
        )
        assert "<= ?" in result.expression
        assert result.params == (value,)

    def test_between(self):
        """Test BETWEEN operator with tuple of two values."""
        low = date(2024, 1, 1)
        high = date(2024, 12, 31)
        result = prepare_expression(
            _fn(Field.DATE, Operator.BETWEEN, (low, high)), DATE_COL
        )
        assert "BETWEEN" in result.expression
        assert "AND" in result.expression
        assert result.params == (low, high)

    def test_not_between(self):
        """Test NOT_BETWEEN operator with tuple of two values."""
        low = Decimal("10")
        high = Decimal("20")
        result = prepare_expression(
            _fn(Field.AMOUNT, Operator.NOT_BETWEEN, (low, high)), AMOUNT_COL
        )
        assert "NOT BETWEEN" in result.expression
        assert result.params == (low, high)

    def test_in(self):
        """Test IN operator with tuple of values."""
        values = ("a", "b", "c")
        result = prepare_expression(_fn(Field.SECURITY, Operator.IN, values), NAME_COL)
        assert "IN" in result.expression
        assert result.params == values

    def test_not_in(self):
        """Test NOT_IN operator with tuple of values."""
        values = ("x", "y")
        result = prepare_expression(
            _fn(Field.SECURITY, Operator.NOT_IN, values), NAME_COL
        )
        assert "NOT IN" in result.expression
        assert result.params == values

    # --- Error path: guard mismatches fall through to case _ ---

    def test_regex_match_non_string_raises(self):
        """Test REGEX_MATCH with non-string value raises OperationError."""
        with pytest.raises(OperationError):
            prepare_expression(
                _fn(Field.DESCRIPTION, Operator.REGEX_MATCH, Decimal("5")), NAME_COL
            )

    def test_not_regex_match_non_string_raises(self):
        """Test NOT_REGEX_MATCH with non-string value raises OperationError."""
        with pytest.raises(OperationError):
            prepare_expression(
                _fn(
                    Field.DESCRIPTION,
                    Operator.NOT_REGEX_MATCH,
                    date(2024, 1, 1),
                ),
                NAME_COL,
            )

    def test_between_wrong_tuple_length_raises(self):
        """Test BETWEEN with 1-tuple raises OperationError."""
        with pytest.raises(OperationError):
            prepare_expression(
                _fn(Field.AMOUNT, Operator.BETWEEN, (Decimal("1"),)), AMOUNT_COL
            )

    def test_in_non_tuple_raises(self):
        """Test IN with non-tuple value raises OperationError."""
        with pytest.raises(OperationError):
            prepare_expression(_fn(Field.SECURITY, Operator.IN, "x"), NAME_COL)


# ============================================================================
# Phase 2: TestGenerateQueryFromFilters (10 tests)
# ============================================================================


class TestGenerateQueryFromFilters:
    """Tests for generate_query_from_filters function."""

    def test_empty_filters_returns_no_where_clause(self):
        """Test that empty filters list produces query without WHERE clause."""
        mappings = {Field.SECURITY: (NAME_COL,)}
        result = generate_query_from_filters([], mappings)
        # Empty query should not contain WHERE
        sql = str(result)
        assert "WHERE" not in sql

    def test_single_filter_single_column(self):
        """Test single filter with single column mapping."""
        filters = [_fn(Field.SECURITY, Operator.EQUALS, "acme")]
        mappings = {Field.SECURITY: (NAME_COL,)}
        result = generate_query_from_filters(filters, mappings)
        sql = str(result)
        assert "WHERE" in sql
        assert "= ?" in sql
        assert result.params == ("acme",)

    def test_single_filter_multiple_columns_generates_or(self):
        """Test single filter mapped to multiple columns generates OR condition."""
        filters = [_fn(Field.SECURITY, Operator.EQUALS, "acme")]
        # Single filter maps to two columns
        mappings = {Field.SECURITY: (NAME_COL, AMOUNT_COL)}
        result = generate_query_from_filters(filters, mappings)
        sql = str(result)
        assert "WHERE" in sql
        # Two columns with same filter should be OR'd together
        assert "OR" in sql
        assert sql.count("=") >= 2
        assert result.params == ("acme", "acme")

    def test_two_filters_different_fields_generates_and(self):
        """Test two filters on different fields are combined with AND."""
        filters = [
            _fn(Field.SECURITY, Operator.EQUALS, "acme"),
            _fn(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100")),
        ]
        mappings = {
            Field.SECURITY: (NAME_COL,),
            Field.AMOUNT: (AMOUNT_COL,),
        }
        result = generate_query_from_filters(filters, mappings)
        sql = str(result)
        # Should have both WHERE conditions combined with AND
        assert "WHERE" in sql
        assert "AND" in sql
        assert "=" in sql
        assert ">" in sql

    def test_two_filters_same_field_generates_or(self):
        """Test two filters on same field are combined with OR."""
        filters = [
            _fn(Field.SECURITY, Operator.EQUALS, "acme"),
            _fn(Field.SECURITY, Operator.EQUALS, "beta"),
        ]
        mappings = {Field.SECURITY: (NAME_COL,)}
        result = generate_query_from_filters(filters, mappings)
        sql = str(result)
        assert "WHERE" in sql
        # Two filters on same field should be OR'd
        assert "OR" in sql
        assert result.params == ("acme", "beta")

    def test_include_fields_excludes_unmatched_filter(self):
        """Test include_fields parameter excludes filters not in the set."""
        filters = [
            _fn(Field.SECURITY, Operator.EQUALS, "acme"),
            _fn(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100")),
        ]
        mappings = {
            Field.SECURITY: (NAME_COL,),
            Field.AMOUNT: (AMOUNT_COL,),
        }
        # Only include AMOUNT field
        result = generate_query_from_filters(
            filters, mappings, include_fields={Field.AMOUNT}
        )
        sql = str(result)
        # Should only have AMOUNT condition
        assert ">" in sql
        assert "=" not in sql
        assert result.params == ("100",)

    def test_include_fields_includes_matched_filter(self):
        """Test include_fields parameter includes only specified fields."""
        filters = [
            _fn(Field.SECURITY, Operator.EQUALS, "acme"),
            _fn(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100")),
        ]
        mappings = {
            Field.SECURITY: (NAME_COL,),
            Field.AMOUNT: (AMOUNT_COL,),
        }
        # Include both fields
        result = generate_query_from_filters(
            filters, mappings, include_fields={Field.SECURITY, Field.AMOUNT}
        )
        sql = str(result)
        # Should have both conditions
        assert "=" in sql
        assert ">" in sql

    def test_include_fields_none_processes_all_filters(self):
        """Test include_fields=None (default) processes all filters."""
        filters = [
            _fn(Field.SECURITY, Operator.EQUALS, "acme"),
            _fn(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100")),
        ]
        mappings = {
            Field.SECURITY: (NAME_COL,),
            Field.AMOUNT: (AMOUNT_COL,),
        }
        result = generate_query_from_filters(filters, mappings, include_fields=None)
        sql = str(result)
        # Should have both conditions
        assert "=" in sql
        assert ">" in sql

    def test_unmapped_field_raises_query_syntax_error(self):
        """Test unmapped field in filters raises QuerySyntaxError."""
        filters = [_fn(Field.SECURITY, Operator.EQUALS, "acme")]
        # Empty mappings - SECURITY not mapped
        mappings: dict[Field, tuple[Col, ...]] = {}
        with pytest.raises(QuerySyntaxError):
            generate_query_from_filters(filters, mappings)

    def test_include_fields_with_unmapped_required_field_raises(self):
        """Test include_fields with unmapped field raises QuerySyntaxError."""
        filters = [
            _fn(Field.SECURITY, Operator.EQUALS, "acme"),
            _fn(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100")),
        ]
        # Only SECURITY is mapped, AMOUNT is not
        mappings = {Field.SECURITY: (NAME_COL,)}
        # Include AMOUNT in filters but not in mappings
        with pytest.raises(QuerySyntaxError):
            generate_query_from_filters(
                filters, mappings, include_fields={Field.AMOUNT}
            )

"""Tests for query preparation and optimization."""

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import column

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.core.query.prepare import (
    combine_filters,
    get_fields_from_queries,
    get_filters_from_queries,
    group_filters,
    prepare_expression,
    prepare_filters,
)
from niveshpy.exceptions import QuerySyntaxError


class TestGroupFilters:
    """Tests for group_filters function."""

    def test_group_by_field(self):
        """Test grouping filters by their fields."""
        filters = [
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("100")),
            FilterNode(Field.DATE, Operator.EQUALS, date(2024, 1, 1)),
            FilterNode(Field.AMOUNT, Operator.GREATER_THAN, Decimal("50")),
        ]

        grouped = group_filters(filters, Field.DESCRIPTION)

        assert len(grouped) == 2
        assert len(grouped[Field.AMOUNT]) == 2
        assert len(grouped[Field.DATE]) == 1

    def test_replace_default_field(self):
        """Test that DEFAULT field is replaced with provided default_field."""
        filters = [
            FilterNode(Field.DEFAULT, Operator.REGEX_MATCH, "test"),
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("100")),
        ]

        grouped = group_filters(filters, Field.DESCRIPTION)

        assert Field.DEFAULT not in grouped
        assert len(grouped[Field.DESCRIPTION]) == 1
        assert grouped[Field.DESCRIPTION][0].field == Field.DESCRIPTION

    def test_replace_multiple_default_fields(self):
        """Test that multiple DEFAULT fields are replaced."""
        filters = [
            FilterNode(Field.DEFAULT, Operator.REGEX_MATCH, "test1"),
            FilterNode(Field.DEFAULT, Operator.REGEX_MATCH, "test2"),
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("100")),
        ]

        grouped = group_filters(filters, Field.SECURITY)

        assert Field.DEFAULT not in grouped
        assert len(grouped[Field.SECURITY]) == 2
        assert all(f.field == Field.SECURITY for f in grouped[Field.SECURITY])

    def test_empty_filters(self):
        """Test grouping empty filter list."""
        grouped = group_filters([], Field.DESCRIPTION)
        assert len(grouped) == 0


class TestCombineFilters:
    """Tests for combine_filters function."""

    def test_combine_equals_into_in(self):
        """Test combining multiple EQUALS into single IN operator."""
        filters = [
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("100")),
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("200")),
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("300")),
        ]

        combined = combine_filters(Field.AMOUNT, filters)

        assert len(combined) == 1
        assert combined[0].operator == Operator.IN
        assert combined[0].value == (Decimal("100"), Decimal("200"), Decimal("300"))

    def test_combine_not_equals_into_not_in(self):
        """Test combining multiple NOT_EQUALS into single NOT_IN operator."""
        filters = [
            FilterNode(Field.TYPE, Operator.NOT_EQUALS, "debit"),
            FilterNode(Field.TYPE, Operator.NOT_EQUALS, "credit"),
        ]

        combined = combine_filters(Field.TYPE, filters)

        assert len(combined) == 1
        assert combined[0].operator == Operator.NOT_IN
        assert combined[0].value == ("debit", "credit")

    def test_combine_existing_in_operators(self):
        """Test combining existing IN operators."""
        filters = [
            FilterNode(Field.AMOUNT, Operator.IN, (Decimal("100"), Decimal("200"))),
            FilterNode(Field.AMOUNT, Operator.IN, (Decimal("300"), Decimal("400"))),
        ]

        combined = combine_filters(Field.AMOUNT, filters)

        assert len(combined) == 1
        assert combined[0].operator == Operator.IN
        assert combined[0].value == (
            Decimal("100"),
            Decimal("200"),
            Decimal("300"),
            Decimal("400"),
        )

    def test_do_not_combine_different_operators(self):
        """Test that different operators are not combined."""
        filters = [
            FilterNode(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100")),
            FilterNode(Field.AMOUNT, Operator.LESS_THAN, Decimal("200")),
            FilterNode(Field.AMOUNT, Operator.BETWEEN, (Decimal("50"), Decimal("150"))),
        ]

        combined = combine_filters(Field.AMOUNT, filters)

        assert len(combined) == 3
        assert all(f in combined for f in filters)

    def test_mix_combinable_and_non_combinable(self):
        """Test combining filters with mixed operators."""
        filters = [
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("100")),
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("200")),
            FilterNode(Field.AMOUNT, Operator.GREATER_THAN, Decimal("50")),
        ]

        combined = combine_filters(Field.AMOUNT, filters)

        assert len(combined) == 2
        # One IN operator with two values
        in_filters = [f for f in combined if f.operator == Operator.IN]
        assert len(in_filters) == 1
        assert in_filters[0].value == (Decimal("100"), Decimal("200"))
        # One GREATER_THAN
        gt_filters = [f for f in combined if f.operator == Operator.GREATER_THAN]
        assert len(gt_filters) == 1

    def test_single_filter_unchanged(self):
        """Test that single non-combinable filter remains unchanged."""
        filters = [
            FilterNode(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100")),
        ]

        combined = combine_filters(Field.AMOUNT, filters)

        assert len(combined) == 1
        assert combined[0] == filters[0]


class TestPrepareFilters:
    """Tests for prepare_filters function."""

    def test_prepare_with_default_field_and_combining(self):
        """Test preparing filters replaces DEFAULT and combines operators."""
        filters = [
            FilterNode(Field.DEFAULT, Operator.REGEX_MATCH, "test"),
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("100")),
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("200")),
        ]

        prepared = prepare_filters(filters, Field.DESCRIPTION)

        # Should have 2 filters: one for DESCRIPTION, one IN for AMOUNT
        assert len(prepared) == 2

        desc_filters = [f for f in prepared if f.field == Field.DESCRIPTION]
        assert len(desc_filters) == 1
        assert desc_filters[0].operator == Operator.REGEX_MATCH

        amt_filters = [f for f in prepared if f.field == Field.AMOUNT]
        assert len(amt_filters) == 1
        assert amt_filters[0].operator == Operator.IN
        assert amt_filters[0].value == (Decimal("100"), Decimal("200"))

    def test_prepare_empty_filters(self):
        """Test preparing empty filter list."""
        prepared = prepare_filters([], Field.DESCRIPTION)
        assert len(prepared) == 0


class TestPrepareExpression:
    """Tests for prepare_expression function."""

    @pytest.mark.parametrize(
        "operator,field,value,col_name",
        [
            (Operator.REGEX_MATCH, Field.DESCRIPTION, "test", "description"),
            (Operator.NOT_REGEX_MATCH, Field.DESCRIPTION, "test", "description"),
            (Operator.EQUALS, Field.AMOUNT, Decimal("100"), "amount"),
            (Operator.NOT_EQUALS, Field.AMOUNT, Decimal("100"), "amount"),
        ],
        ids=["regex_match", "not_regex_match", "equals", "not_equals"],
    )
    def test_binary_operators(self, operator, field, value, col_name):
        """Test binary operators create appropriate SQLAlchemy expressions."""
        filter_node = FilterNode(field, operator, value)
        col = column(col_name)

        expr = prepare_expression(filter_node, col)

        assert hasattr(expr, "type")

    @pytest.mark.parametrize(
        "operator",
        [
            Operator.GREATER_THAN,
            Operator.GREATER_THAN_EQ,
            Operator.LESS_THAN,
            Operator.LESS_THAN_EQ,
        ],
    )
    def test_comparison_operators(self, operator):
        """Test comparison operators create appropriate expressions."""
        filter_node = FilterNode(Field.AMOUNT, operator, Decimal("100"))
        col = column("amount")

        expr = prepare_expression(filter_node, col)

        assert hasattr(expr, "type")

    @pytest.mark.parametrize(
        "operator,field,value,col_name",
        [
            (
                Operator.BETWEEN,
                Field.AMOUNT,
                (Decimal("100"), Decimal("200")),
                "amount",
            ),
            (
                Operator.NOT_BETWEEN,
                Field.DATE,
                (date(2024, 1, 1), date(2024, 12, 31)),
                "date",
            ),
        ],
        ids=["between", "not_between"],
    )
    def test_between_operators(self, operator, field, value, col_name):
        """Test BETWEEN/NOT_BETWEEN operators create appropriate expressions."""
        filter_node = FilterNode(field, operator, value)
        col = column(col_name)

        expr = prepare_expression(filter_node, col)

        assert hasattr(expr, "type")

    @pytest.mark.parametrize(
        "operator,field,value,col_name",
        [
            (
                Operator.IN,
                Field.AMOUNT,
                (Decimal("100"), Decimal("200"), Decimal("300")),
                "amount",
            ),
            (Operator.NOT_IN, Field.TYPE, ("debit", "credit"), "type"),
        ],
        ids=["in", "not_in"],
    )
    def test_in_operators(self, operator, field, value, col_name):
        """Test IN/NOT_IN operators create appropriate expressions."""
        filter_node = FilterNode(field, operator, value)
        col = column(col_name)

        expr = prepare_expression(filter_node, col)

        assert hasattr(expr, "type")

    def test_unsupported_operator_raises_error(self):
        """Test unsupported operator/value combination raises OperationError."""
        from niveshpy.exceptions import OperationError

        # Create invalid filter (e.g., BETWEEN with non-tuple value)
        filter_node = FilterNode(Field.AMOUNT, Operator.BETWEEN, Decimal("100"))
        col = column("amount")

        with pytest.raises(OperationError, match="Unsupported operator"):
            prepare_expression(filter_node, col)


class TestGetFiltersFromQueries:
    """Tests for get_filters_from_queries function."""

    def test_single_query_single_filter(self, column_map):
        """Test processing single query with one filter."""
        queries = ("amt:100",)

        expressions = get_filters_from_queries(queries, Field.DESCRIPTION, column_map)

        assert len(expressions) == 1

    def test_multiple_queries(self, column_map):
        """Test processing multiple query strings."""
        queries = ("amt:100", "date:2024-01-01")

        expressions = get_filters_from_queries(queries, Field.DESCRIPTION, column_map)

        assert len(expressions) == 2

    def test_default_field_resolution(self, column_map):
        """Test that DEFAULT field is resolved to default_field parameter."""
        queries = ("grocery",)

        expressions = get_filters_from_queries(queries, Field.DESCRIPTION, column_map)

        assert len(expressions) == 1

    def test_combining_happens(self, column_map):
        """Test that multiple EQUALS are combined into IN."""
        queries = ("amt:100", "amt:200")

        expressions = get_filters_from_queries(queries, Field.DESCRIPTION, column_map)

        # Should be combined into single IN expression
        assert len(expressions) == 1

    def test_unmapped_field_raises_error(self):
        """Test that unmapped field raises QuerySyntaxError."""
        queries = ("sec:AAPL",)
        # Column map without SECURITY field
        column_map = {
            Field.AMOUNT: ["amount"],
            Field.DATE: ["date"],
        }

        with pytest.raises(QuerySyntaxError, match="not mapped"):
            get_filters_from_queries(queries, Field.DESCRIPTION, column_map)

    def test_syntax_error_during_parsing(self):
        """Test that syntax errors during parsing are caught and re-raised."""
        queries = ("amt:invalid",)
        column_map = {Field.AMOUNT: ["amount"]}

        with pytest.raises(QuerySyntaxError):
            get_filters_from_queries(queries, Field.DESCRIPTION, column_map)

    def test_exception_handler_in_get_filters(self, column_map):
        """Test that exception handler at lines 177-179 catches and re-raises with context."""
        queries = ("amt:abc123xyz",)  # Invalid number format

        with pytest.raises(QuerySyntaxError) as exc_info:
            get_filters_from_queries(queries, Field.DESCRIPTION, column_map)

        # Verify the exception was caught and re-raised
        # The exception message should contain error information
        assert "Invalid token" in str(exc_info.value)


class TestGetFieldsFromQueries:
    """Tests for get_fields_from_queries function."""

    def test_single_field(self):
        """Test extracting single field from query."""
        queries = ("amt:100",)

        fields = get_fields_from_queries(queries)

        assert fields == {Field.AMOUNT}

    def test_multiple_fields(self):
        """Test extracting multiple fields from queries."""
        queries = ("amt:100", "date:2024-01-01", "acct:savings")

        fields = get_fields_from_queries(queries)

        assert fields == {Field.AMOUNT, Field.DATE, Field.ACCOUNT}

    def test_duplicate_fields(self):
        """Test that duplicate fields are deduplicated."""
        queries = ("amt:100", "amt:200", "amt:>50")

        fields = get_fields_from_queries(queries)

        assert fields == {Field.AMOUNT}

    def test_default_field_preserved(self):
        """Test that DEFAULT field is preserved (not resolved)."""
        queries = ("grocery",)

        fields = get_fields_from_queries(queries)

        assert fields == {Field.DEFAULT}

    def test_empty_queries(self):
        """Test extracting fields from empty queries."""
        queries = ("",)

        fields = get_fields_from_queries(queries)

        assert fields == set()

    def test_invalid_query_raises_error(self):
        """Test that invalid query syntax raises QuerySyntaxError."""
        queries = ("amt:invalid",)

        with pytest.raises(QuerySyntaxError):
            get_fields_from_queries(queries)

    def test_exception_reraise_with_context(self):
        """Test that exception handler at lines 218-220 catches and re-raises with context."""
        # Force the lazy iterator to evaluate by converting the result
        queries = ("amt:invalid_value",)

        with pytest.raises(QuerySyntaxError) as exc_info:
            # The function needs to iterate to trigger the exception
            get_fields_from_queries(queries)

        # Verify exception was raised with proper error information
        assert "Invalid token sequence" in str(exc_info.value)

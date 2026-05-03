"""Tests for query_filters module."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import column

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.infrastructure.sqlite.query_filters import prepare_expression


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

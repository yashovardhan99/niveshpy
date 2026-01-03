"""Tests for query parser."""

from datetime import date
from decimal import Decimal

import pytest

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.core.query.tokens import Int, Keyword, Literal, Unknown
from niveshpy.exceptions import QuerySyntaxError


@pytest.mark.parametrize(
    "query,expected_filter",
    [
        # Exact amounts
        ("amt:100", FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("100"))),
        ("amt:100.50", FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("100.50"))),
        ("amt:0", FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("0"))),
        (
            "amt:999999.99",
            FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("999999.99")),
        ),
        # Amount comparisons
        ("amt:>100", FilterNode(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100"))),
        (
            "amt:>=100",
            FilterNode(Field.AMOUNT, Operator.GREATER_THAN_EQ, Decimal("100")),
        ),
        ("amt:<100", FilterNode(Field.AMOUNT, Operator.LESS_THAN, Decimal("100"))),
        ("amt:<=100", FilterNode(Field.AMOUNT, Operator.LESS_THAN_EQ, Decimal("100"))),
        # Amount ranges
        (
            "amt:100..200",
            FilterNode(
                Field.AMOUNT, Operator.BETWEEN, (Decimal("100"), Decimal("200"))
            ),
        ),
        (
            "amt:0..100",
            FilterNode(Field.AMOUNT, Operator.BETWEEN, (Decimal("0"), Decimal("100"))),
        ),
        # One-sided open ranges
        (
            "amt:100..",
            FilterNode(Field.AMOUNT, Operator.GREATER_THAN_EQ, Decimal("100")),
        ),
        ("amt:..100", FilterNode(Field.AMOUNT, Operator.LESS_THAN_EQ, Decimal("100"))),
    ],
    ids=[
        "exact_integer",
        "exact_decimal",
        "exact_zero",
        "exact_large",
        "greater_than",
        "greater_equal",
        "less_than",
        "less_equal",
        "closed_range",
        "range_from_zero",
        "open_range_start",
        "open_range_end",
    ],
)
def test_parse_amount_expressions(parse_query, query, expected_filter):
    """Test parsing amount expressions."""
    filters = parse_query(query)
    assert len(filters) == 1
    assert filters[0] == expected_filter


@pytest.mark.parametrize(
    "query,expected_filter",
    [
        # Full dates
        ("date:2024-01-15", FilterNode(Field.DATE, Operator.EQUALS, date(2024, 1, 15))),
        (
            "date:2024-12-31",
            FilterNode(Field.DATE, Operator.EQUALS, date(2024, 12, 31)),
        ),
        # Year only
        (
            "date:2024",
            FilterNode(
                Field.DATE, Operator.BETWEEN, (date(2024, 1, 1), date(2024, 12, 31))
            ),
        ),
        # Year-month
        (
            "date:2024-01",
            FilterNode(
                Field.DATE, Operator.BETWEEN, (date(2024, 1, 1), date(2024, 1, 31))
            ),
        ),
        (
            "date:2024-02",
            FilterNode(
                Field.DATE, Operator.BETWEEN, (date(2024, 2, 1), date(2024, 2, 29))
            ),
        ),  # Leap year
        (
            "date:2023-02",
            FilterNode(
                Field.DATE, Operator.BETWEEN, (date(2023, 2, 1), date(2023, 2, 28))
            ),
        ),  # Non-leap year
        # Date ranges
        (
            "date:2024-01-01..2024-12-31",
            FilterNode(
                Field.DATE, Operator.BETWEEN, (date(2024, 1, 1), date(2024, 12, 31))
            ),
        ),
        # One-sided open ranges
        (
            "date:2024-01..",
            FilterNode(Field.DATE, Operator.GREATER_THAN_EQ, date(2024, 1, 1)),
        ),
        (
            "date:..2024-12-31",
            FilterNode(Field.DATE, Operator.LESS_THAN_EQ, date(2024, 12, 31)),
        ),
    ],
    ids=[
        "full_date",
        "full_date_end_of_year",
        "year_only",
        "year_month",
        "year_month_leap",
        "year_month_non_leap",
        "date_range",
        "open_range_start",
        "open_range_end",
    ],
)
def test_parse_date_expressions(parse_query, query, expected_filter):
    """Test parsing date expressions."""
    filters = parse_query(query)
    assert len(filters) == 1
    assert filters[0] == expected_filter


@pytest.mark.parametrize(
    "query,expected_filter",
    [
        ("acct:savings", FilterNode(Field.ACCOUNT, Operator.REGEX_MATCH, "savings")),
        (
            "desc:payment",
            FilterNode(Field.DESCRIPTION, Operator.REGEX_MATCH, "payment"),
        ),
        ("type:credit", FilterNode(Field.TYPE, Operator.REGEX_MATCH, "credit")),
        ("sec:AAPL", FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "AAPL")),
    ],
    ids=["account", "description", "type", "security"],
)
def test_parse_field_keywords(parse_query, query, expected_filter):
    """Test parsing field keywords."""
    filters = parse_query(query)
    assert len(filters) == 1
    assert filters[0] == expected_filter


@pytest.mark.parametrize(
    "query,expected_filters",
    [
        # Not with text (uses DEFAULT field)
        (
            "not:cancelled",
            [FilterNode(Field.DEFAULT, Operator.NOT_REGEX_MATCH, "cancelled")],
        ),
        # Not with amount
        (
            "not:amt:100",
            [FilterNode(Field.AMOUNT, Operator.NOT_EQUALS, Decimal("100"))],
        ),
        (
            "not:amt:>100",
            [FilterNode(Field.AMOUNT, Operator.LESS_THAN_EQ, Decimal("100"))],
        ),
        (
            "not:amt:>=100",
            [FilterNode(Field.AMOUNT, Operator.LESS_THAN, Decimal("100"))],
        ),
        (
            "not:amt:<100",
            [FilterNode(Field.AMOUNT, Operator.GREATER_THAN_EQ, Decimal("100"))],
        ),
        (
            "not:amt:<=100",
            [FilterNode(Field.AMOUNT, Operator.GREATER_THAN, Decimal("100"))],
        ),
        # Not with field keywords (all use NOT_REGEX_MATCH)
        (
            "not:acct:checking",
            [FilterNode(Field.ACCOUNT, Operator.NOT_REGEX_MATCH, "checking")],
        ),
        (
            "not:desc:refund",
            [FilterNode(Field.DESCRIPTION, Operator.NOT_REGEX_MATCH, "refund")],
        ),
        ("not:type:debit", [FilterNode(Field.TYPE, Operator.NOT_REGEX_MATCH, "debit")]),
        (
            "not:sec:MSFT",
            [FilterNode(Field.SECURITY, Operator.NOT_REGEX_MATCH, "MSFT")],
        ),
        # Not with date
        (
            "not:date:2024-01-01",
            [FilterNode(Field.DATE, Operator.NOT_EQUALS, date(2024, 1, 1))],
        ),
        (
            "not:date:2024",
            [
                FilterNode(
                    Field.DATE,
                    Operator.NOT_BETWEEN,
                    (date(2024, 1, 1), date(2024, 12, 31)),
                )
            ],
        ),
    ],
    ids=[
        "not_text",
        "not_amount_equals",
        "not_amount_gt",
        "not_amount_gte",
        "not_amount_lt",
        "not_amount_lte",
        "not_account",
        "not_description",
        "not_type",
        "not_security",
        "not_date_full",
        "not_date_year",
    ],
)
def test_parse_negation(parse_query, query, expected_filters):
    """Test parsing negation with NOT keyword."""
    filters = parse_query(query)
    assert filters == expected_filters


@pytest.mark.parametrize(
    "query,expected_count,expected_value",
    [
        ("grocery", 1, "grocery"),
        ("grocery store payment", 1, "grocery store payment"),
        ("", 0, None),
    ],
    ids=["single_word", "multiple_words", "empty"],
)
def test_parse_text_queries(parse_query, query, expected_count, expected_value):
    """Test parsing plain text and empty queries."""
    filters = parse_query(query)
    assert len(filters) == expected_count
    if expected_count > 0:
        assert filters[0].field == Field.DEFAULT
        assert filters[0].operator == Operator.REGEX_MATCH
        assert filters[0].value == expected_value


@pytest.mark.parametrize(
    "query,error_match",
    [
        ("amt:abc", "Invalid token"),
        ("date:invalid", "Invalid token"),
        ("amt:>", "Invalid token"),
        ("date:>", "Invalid token"),
        ("amt:..", "start and end amount cannot be empty"),
        ("date:..", "start date and end date cannot be empty"),
        ("amt:200..100", "start amount is greater than end amount"),
        ("date:2024-12-31..2024-01-01", "start date is after end date"),
        ("date:2024-02-30", "Invalid date"),
    ],
    ids=[
        "amount_invalid",
        "date_invalid",
        "amount_comparison_missing",
        "date_comparison_missing",
        "amount_empty_range",
        "date_empty_range",
        "amount_inverted_range",
        "date_inverted_range",
        "date_invalid_day",
    ],
)
def test_parse_errors(parse_query, query, error_match):
    """Test parsing invalid queries raises appropriate errors."""
    with pytest.raises(QuerySyntaxError, match=error_match):
        parse_query(query)


def test_parse_amount_equal_range(parse_query):
    """Test amount range where start equals end becomes EQUALS."""
    filters = parse_query("amt:100..100")

    assert len(filters) == 1
    assert filters[0].operator == Operator.EQUALS
    assert filters[0].value == Decimal("100")


@pytest.mark.parametrize(
    "query,expected_filter",
    [
        ("amt:-100", FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("-100"))),
        ("amt:-0.50", FilterNode(Field.AMOUNT, Operator.EQUALS, Decimal("-0.50"))),
    ],
    ids=[
        "negative_integer",
        "negative_decimal",
    ],
)
def test_parse_negative_amount(parse_query, query, expected_filter):
    """Test parsing negative amounts."""
    filters = parse_query(query)

    assert len(filters) == 1
    assert filters[0] == expected_filter


@pytest.mark.parametrize(
    "query,expected_range",
    [
        ("date:2024-12", (date(2024, 12, 1), date(2024, 12, 31))),
        ("date:2024", (date(2024, 1, 1), date(2024, 12, 31))),
    ],
    ids=["year_month_december", "year_only"],
)
def test_parse_year_ranges(parse_query, query, expected_range):
    """Test year and year-month date ranges."""
    filters = parse_query(query)

    assert len(filters) == 1
    assert filters[0].operator == Operator.BETWEEN
    assert filters[0].value == expected_range


def test_get_operator_from_token_error():
    """Test that get_operator_from_token raises error for unexpected tokens."""
    from niveshpy.core.query.parser import QueryParser
    from niveshpy.core.query.tokenizer import QueryLexer
    from niveshpy.core.query.tokens import Literal
    from niveshpy.exceptions import OperationError

    parser = QueryParser(QueryLexer("test"))

    with pytest.raises(OperationError, match="Unexpected token"):
        parser.get_operator_from_token(Literal("x"))


class TestConvertToString:
    """Test convert_to_string with various token types."""

    @pytest.mark.parametrize(
        "token,expected_result",
        [
            (Literal("hello"), "hello"),
            (Int("123"), "123"),
            (Unknown("@", 0), "@"),
            (Keyword.Amount, "amt"),
        ],
        ids=["literal", "int", "unknown", "keyword"],
    )
    def test_convert_single_token_to_string(self, token, expected_result):
        """Test converting various single token types to string."""
        from niveshpy.core.query.parser import QueryParser

        result = QueryParser.convert_to_string([token])
        assert result == expected_result

    def test_convert_mixed_tokens(self):
        """Test converting mixed token types to string."""
        from niveshpy.core.query.parser import QueryParser
        from niveshpy.core.query.tokens import Colon, Int, Literal, Unknown

        tokens = [Literal("test"), Colon(), Int("123"), Unknown("@", 0)]
        result = QueryParser.convert_to_string(tokens)
        assert result == "test:123@"

    def test_convert_to_string_unexpected_token(self):
        """Test convert_to_string with unexpected token type."""
        from niveshpy.core.query.parser import QueryParser
        from niveshpy.core.query.tokens import End
        from niveshpy.exceptions import OperationError

        with pytest.raises(OperationError, match="Unexpected token"):
            QueryParser.convert_to_string([End()])


class TestConvertToNumber:
    """Test convert_to_number with various token types."""

    def test_convert_to_number_invalid_tokens(self):
        """Test convert_to_number with invalid token sequence."""
        from niveshpy.core.query.parser import QueryParser
        from niveshpy.core.query.tokens import Literal

        with pytest.raises(QuerySyntaxError, match="Invalid token sequence"):
            QueryParser.convert_to_number([Literal("abc")])


class TestSpecialCharacterQueries:
    """Test queries containing special characters."""

    @pytest.mark.parametrize(
        "query,expected_value",
        [
            (":", ":"),
            ("-", "-"),
            (".", "."),
            ("..", ".."),
            (">", ">"),
            (">=", ">="),
            ("<", "<"),
            ("<=", "<="),
            ("test:value", "test:value"),
            ("test123", "test123"),
            ("@test", "@test"),
        ],
        ids=[
            "colon",
            "dash",
            "dot",
            "range_sep",
            "gt",
            "gte",
            "lt",
            "lte",
            "mixed",
            "with_int",
            "unknown_char",
        ],
    )
    def test_special_character_queries(self, query, expected_value):
        """Test queries with special characters are parsed as literals."""
        from niveshpy.core.query.parser import QueryParser
        from niveshpy.core.query.tokenizer import QueryLexer

        parser = QueryParser(QueryLexer(query))
        filters = parser.parse()

        assert len(filters) == 1
        assert filters[0].field == Field.DEFAULT
        assert filters[0].value == expected_value

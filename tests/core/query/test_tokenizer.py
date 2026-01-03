"""Tests for query tokenizer."""

import pytest

from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.core.query.tokens import End, Int, Keyword, Literal


def test_tokenize_simple_literal():
    """Test tokenizing simple literal."""
    tokens = list(QueryLexer("apple"))
    assert len(tokens) == 2
    assert isinstance(tokens[0], Literal)
    assert isinstance(tokens[-1], End)


def test_tokenize_integer():
    """Test tokenizing integer."""
    tokens = list(QueryLexer("100"))
    assert len(tokens) == 2
    assert isinstance(tokens[0], Int)
    assert tokens[0].value == "100"
    assert isinstance(tokens[-1], End)


@pytest.mark.parametrize(
    "query,expected_keyword,expected_min_tokens",
    [
        ("amt:100", Keyword.Amount, 3),
        ("date:2024-01-01", Keyword.Date, 2),
        ("acct:savings", Keyword.Account, 3),
        ("desc:payment", Keyword.Description, 3),
        ("type:credit", Keyword.Type, 3),
        ("sec:AAPL", Keyword.Security, 3),
        ("not:cancelled", Keyword.Not, 3),
    ],
    ids=["amount", "date", "account", "description", "type", "security", "not"],
)
def test_tokenize_keywords(query, expected_keyword, expected_min_tokens):
    """Test tokenizing various keywords."""
    tokens = list(QueryLexer(query))
    assert len(tokens) >= expected_min_tokens
    assert tokens[0] == expected_keyword
    assert isinstance(tokens[-1], End)


def test_tokenize_empty_string():
    """Test tokenizing empty string."""
    tokens = list(QueryLexer(""))
    assert isinstance(tokens[-1], End)


def test_tokenize_quoted_text():
    """Test tokenizing quoted text."""
    tokens = list(QueryLexer('"quoted text"'))
    assert len(tokens) >= 2
    # Should have some token and End
    assert isinstance(tokens[-1], End)


class TestDotTokenization:
    """Tests for dot and range separator tokenization."""

    def test_single_dot(self):
        """Test that single dot creates Dot token."""
        from niveshpy.core.query.tokens import Dot

        lexer = QueryLexer(".")
        token = lexer.next_token()

        assert isinstance(token, Dot)

    def test_double_dot(self):
        """Test that double dot creates RangeSeparator token."""
        from niveshpy.core.query.tokens import RangeSeparator

        lexer = QueryLexer("..")
        token = lexer.next_token()

        assert isinstance(token, RangeSeparator)

    def test_dot_followed_by_char(self):
        """Test dot followed by non-dot character creates separate tokens."""
        from niveshpy.core.query.tokens import Dot, Literal

        lexer = QueryLexer(".x")
        token1 = lexer.next_token()
        token2 = lexer.next_token()

        assert isinstance(token1, Dot)
        assert isinstance(token2, Literal)
        assert token2.value == "x"

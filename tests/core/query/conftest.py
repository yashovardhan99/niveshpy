"""Fixtures for query system tests."""

import pytest

from niveshpy.core.query.ast import Field
from niveshpy.core.query.parser import QueryParser
from niveshpy.core.query.tokenizer import QueryLexer


@pytest.fixture
def column_map():
    """Return a mapping of Field enums to column names for testing."""
    return {
        Field.AMOUNT: ["amount"],
        Field.DATE: ["transaction_date"],
        Field.DESCRIPTION: ["description"],
        Field.ACCOUNT: ["account_name"],
        Field.TYPE: ["type"],
        Field.SECURITY: ["security_key"],
    }


@pytest.fixture
def parse_query():
    """Return a function that parses a query string."""

    def _parse(query: str):
        return QueryParser(QueryLexer(query)).parse()

    return _parse

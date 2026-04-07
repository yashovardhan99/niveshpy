"""SQLite security repository unit tests."""

from unittest.mock import patch

import pytest

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.infrastructure.sqlite.repositories import SqliteSecurityRepository
from niveshpy.models.security import SecurityCategory, SecurityCreate, SecurityType


@pytest.fixture(scope="function")
def security_repository(session):
    """Provide a fresh SqliteSecurityRepository for each test."""
    with patch(
        "niveshpy.infrastructure.sqlite.repositories.sqlite_security_repository.get_session",
        return_value=session,  # This session is defined in a higher-level fixture.
    ):
        yield SqliteSecurityRepository()


def test_insert_security_returns_true_and_persists_row(
    security_repository: SqliteSecurityRepository,
) -> None:
    """Inserting a security returns True and persists the row."""
    result = security_repository.insert_security(
        SecurityCreate(
            key="INF123",
            name="Infrastructure Fund",
            category=SecurityCategory.EQUITY,
            type=SecurityType.MUTUAL_FUND,
            properties={"source": "test"},
        )
    )
    assert result is True

    securities = security_repository.find_securities([])
    assert len(securities) == 1
    assert securities[0].key == "INF123"
    assert securities[0].name == "Infrastructure Fund"
    assert securities[0].category is SecurityCategory.EQUITY
    assert securities[0].type is SecurityType.MUTUAL_FUND
    assert securities[0].properties.get("source") == "test"


def test_insert_security_duplicate_returns_false_and_does_not_insert(
    security_repository: SqliteSecurityRepository,
) -> None:
    """Inserting a duplicate security returns False and does not insert a new row."""
    first_result = security_repository.insert_security(
        SecurityCreate(
            key="INF123",
            name="Infrastructure Fund",
            category=SecurityCategory.EQUITY,
            type=SecurityType.MUTUAL_FUND,
            properties={"source": "test"},
        )
    )
    assert first_result is True

    duplicate_result = security_repository.insert_security(
        SecurityCreate(
            key="INF123",
            name="Duplicate Fund",
            category=SecurityCategory.DEBT,
            type=SecurityType.BOND,
            properties={"source": "test2"},
        )
    )
    assert duplicate_result is False

    securities = security_repository.find_securities([])
    assert len(securities) == 1
    assert securities[0].key == "INF123"
    assert securities[0].name == "Infrastructure Fund"
    assert securities[0].category is SecurityCategory.EQUITY
    assert securities[0].type is SecurityType.MUTUAL_FUND
    assert securities[0].properties.get("source") == "test"


def test_find_securities_applies_filter_limit_and_offset(
    security_repository: SqliteSecurityRepository,
) -> None:
    """Finding securities applies key filter, limit, and offset correctly."""
    count = security_repository.insert_multiple_securities(
        [
            SecurityCreate(
                key="AAA111",
                name="Alpha Fund",
                category=SecurityCategory.EQUITY,
                type=SecurityType.MUTUAL_FUND,
            ),
            SecurityCreate(
                key="BBB222",
                name="Beta Fund",
                category=SecurityCategory.DEBT,
                type=SecurityType.BOND,
            ),
            SecurityCreate(
                key="CCC333",
                name="Gamma Fund",
                category=SecurityCategory.COMMODITY,
                type=SecurityType.ETF,
            ),
        ]
    )
    assert count == 3

    filtered = security_repository.find_securities(
        [FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "B")]
    )
    assert len(filtered) == 1
    assert filtered[0].key == "BBB222"

    paged = security_repository.find_securities([], limit=1, offset=1)
    assert len(paged) == 1
    assert paged[0].key == "BBB222"


def test_find_securities_by_keys_returns_subset_and_empty_input_is_empty(
    security_repository: SqliteSecurityRepository,
) -> None:
    """Finding securities by keys returns subset of matches and empty input returns empty."""
    security_repository.insert_multiple_securities(
        [
            SecurityCreate(
                key="AAA111",
                name="Alpha Fund",
                category=SecurityCategory.EQUITY,
                type=SecurityType.MUTUAL_FUND,
            ),
            SecurityCreate(
                key="BBB222",
                name="Beta Fund",
                category=SecurityCategory.DEBT,
                type=SecurityType.BOND,
            ),
            SecurityCreate(
                key="CCC333",
                name="Gamma Fund",
                category=SecurityCategory.COMMODITY,
                type=SecurityType.ETF,
            ),
        ]
    )

    subset = security_repository.find_securities_by_keys(["AAA111", "CCC333"])
    assert len(subset) == 2
    assert {s.key for s in subset} == {"AAA111", "CCC333"}

    empty = security_repository.find_securities_by_keys([])
    assert len(empty) == 0


def test_insert_multiple_securities_counts_only_new_rows(
    security_repository: SqliteSecurityRepository,
) -> None:
    """Inserting multiple securities counts only new rows, not duplicates."""
    first_count = security_repository.insert_multiple_securities(
        [
            SecurityCreate(
                key="AAA111",
                name="Alpha Fund",
                category=SecurityCategory.EQUITY,
                type=SecurityType.MUTUAL_FUND,
            ),
            SecurityCreate(
                key="BBB222",
                name="Beta Fund",
                category=SecurityCategory.DEBT,
                type=SecurityType.BOND,
            ),
        ]
    )
    assert first_count == 2

    duplicate_count = security_repository.insert_multiple_securities(
        [
            SecurityCreate(
                key="AAA111",
                name="Alpha Fund Duplicate",
                category=SecurityCategory.COMMODITY,
                type=SecurityType.ETF,
            ),
            SecurityCreate(
                key="CCC333",
                name="Gamma Fund",
                category=SecurityCategory.COMMODITY,
                type=SecurityType.ETF,
            ),
        ]
    )
    assert duplicate_count == 1

    securities = security_repository.find_securities([])
    assert len(securities) == 3
    assert {s.key for s in securities} == {"AAA111", "BBB222", "CCC333"}


def test_delete_security_by_key_returns_true_then_false(
    security_repository: SqliteSecurityRepository,
) -> None:
    """Deleting a security by key returns True if deleted, then False if not found."""
    security_repository.insert_security(
        SecurityCreate(
            key="DEL123",
            name="Delete Me",
            category=SecurityCategory.EQUITY,
            type=SecurityType.MUTUAL_FUND,
        )
    )

    first_delete = security_repository.delete_security_by_key("DEL123")
    assert first_delete is True

    second_delete = security_repository.delete_security_by_key("DEL123")
    assert second_delete is False

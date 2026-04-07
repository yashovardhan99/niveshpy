"""SQLite account repository unit tests."""

from unittest.mock import patch

import pytest

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.infrastructure.sqlite.repositories import SqliteAccountRepository
from niveshpy.models.account import AccountCreate


@pytest.fixture(scope="function")
def account_repository(session):
    """Provide a fresh SqliteAccountRepository for each test."""
    with patch(
        "niveshpy.infrastructure.sqlite.repositories.sqlite_account_repository.get_session",
        return_value=session,
    ):
        yield SqliteAccountRepository()


def test_insert_account_returns_new_id_and_persists_row(
    account_repository: SqliteAccountRepository,
) -> None:
    """Inserting an account returns the new ID and persists the row."""
    new_id = account_repository.insert_account(
        AccountCreate(name="Primary", institution="HDFC")
    )
    assert new_id == 1

    accounts = account_repository.find_accounts([])
    assert len(accounts) == 1
    assert accounts[0].id == 1
    assert accounts[0].name == "Primary"
    assert accounts[0].institution == "HDFC"


def test_insert_account_duplicate_returns_none_and_does_not_insert(
    account_repository: SqliteAccountRepository,
) -> None:
    """Inserting a duplicate account returns None and does not insert a new row."""
    first_id = account_repository.insert_account(
        AccountCreate(name="Primary", institution="HDFC")
    )
    assert first_id == 1

    duplicate_id = account_repository.insert_account(
        AccountCreate(name="Primary", institution="HDFC")
    )
    assert duplicate_id is None

    accounts = account_repository.find_accounts([])
    assert len(accounts) == 1
    assert accounts[0].id == 1
    assert accounts[0].name == "Primary"
    assert accounts[0].institution == "HDFC"


def test_find_accounts_applies_filter_limit_and_offset(
    account_repository: SqliteAccountRepository,
) -> None:
    """Finding accounts applies name filter, limit, and offset correctly."""
    account_repository.insert_account(AccountCreate(name="Alpha", institution="HDFC"))
    account_repository.insert_account(AccountCreate(name="Beta", institution="ICICI"))
    account_repository.insert_account(AccountCreate(name="Gamma", institution="SBI"))

    filtered = account_repository.find_accounts(
        [
            FilterNode(Field.ACCOUNT, Operator.REGEX_MATCH, "al"),
            FilterNode(Field.ACCOUNT, Operator.REGEX_MATCH, "sbi"),
        ]
    )
    assert len(filtered) == 2
    assert {a.name for a in filtered} == {"Alpha", "Gamma"}

    paged = account_repository.find_accounts([], limit=1, offset=1)
    assert len(paged) == 1
    assert paged[0].name == "Beta"
    assert paged[0].institution == "ICICI"


def test_find_accounts_by_name_and_institutions_returns_exact_pairs(
    account_repository: SqliteAccountRepository,
) -> None:
    """Finding accounts by name and institution returns exact matches."""
    account_repository.insert_account(AccountCreate(name="Primary", institution="HDFC"))
    account_repository.insert_account(
        AccountCreate(name="Primary", institution="ICICI")
    )
    account_repository.insert_account(
        AccountCreate(name="Secondary", institution="HDFC")
    )

    filtered = account_repository.find_accounts_by_name_and_institutions(
        ["Primary", "Primary"], ["HDFC", "ICICI"]
    )
    assert len(filtered) == 2
    assert filtered[0].name == "Primary"
    assert filtered[0].institution == "HDFC"
    assert filtered[1].name == "Primary"
    assert filtered[1].institution == "ICICI"


def test_insert_multiple_accounts_counts_only_new_rows(
    account_repository: SqliteAccountRepository,
) -> None:
    """Inserting multiple accounts counts only new rows, not duplicates."""
    first_count = account_repository.insert_multiple_accounts(
        [
            AccountCreate(name="Primary", institution="HDFC"),
            AccountCreate(name="Secondary", institution="ICICI"),
        ]
    )
    assert first_count == 2

    duplicate_count = account_repository.insert_multiple_accounts(
        [
            AccountCreate(name="Primary", institution="HDFC"),
            AccountCreate(name="Secondary", institution="SBI"),
        ]
    )
    assert duplicate_count == 1

    accounts = account_repository.find_accounts([])
    assert len(accounts) == 3


def test_delete_account_by_id_returns_true_then_false(
    account_repository: SqliteAccountRepository,
) -> None:
    """Deleting an account by ID returns True on first delete, then False."""
    account_id = account_repository.insert_account(
        AccountCreate(name="Disposable", institution="Axis")
    )
    assert account_id == 1

    first_delete = account_repository.delete_account_by_id(account_id)
    assert first_delete is True

    second_delete = account_repository.delete_account_by_id(account_id)
    assert second_delete is False

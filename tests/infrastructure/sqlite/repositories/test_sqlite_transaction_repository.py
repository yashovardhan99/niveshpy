"""SQLite transaction repository unit tests."""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.infrastructure.sqlite.repositories import (
    SqliteAccountRepository,
    SqliteSecurityRepository,
    SqliteTransactionRepository,
)
from niveshpy.models.account import AccountCreate
from niveshpy.models.security import SecurityCategory, SecurityCreate, SecurityType
from niveshpy.models.transaction import TransactionCreate, TransactionType


@pytest.fixture(scope="function")
def transaction_repository(session):
    """Provide a fresh SqliteTransactionRepository for each test."""
    with patch(
        "niveshpy.infrastructure.sqlite.repositories.sqlite_transaction_repository.get_session",
        return_value=session,  # This session is defined in a higher-level fixture.
    ):
        yield SqliteTransactionRepository()


@pytest.fixture(scope="function")
def account_repository(session):
    """Provide a fresh SqliteAccountRepository for each test."""
    with patch(
        "niveshpy.infrastructure.sqlite.repositories.sqlite_account_repository.get_session",
        return_value=session,
    ):
        yield SqliteAccountRepository()


@pytest.fixture(scope="function")
def security_repository(session):
    """Provide a fresh SqliteSecurityRepository for each test."""
    with patch(
        "niveshpy.infrastructure.sqlite.repositories.sqlite_security_repository.get_session",
        return_value=session,
    ):
        yield SqliteSecurityRepository()


def test_insert_transaction_returns_id_and_persists_row(
    transaction_repository: SqliteTransactionRepository,
    account_repository: SqliteAccountRepository,
    security_repository: SqliteSecurityRepository,
) -> None:
    """Inserting a transaction returns id and persists the row."""
    account_repository.insert_account(
        AccountCreate(name="Test Account", institution="Test Bank")
    )
    security_repository.insert_security(
        SecurityCreate(
            key="INF123",
            name="Infrastructure Fund",
            category=SecurityCategory.EQUITY,
            type=SecurityType.MUTUAL_FUND,
        )
    )
    result = transaction_repository.insert_transaction(
        TransactionCreate(
            account_id=1,
            security_key="INF123",
            transaction_date=datetime.date(2024, 1, 1),
            units=Decimal(100),
            amount=Decimal(1000),
            type=TransactionType.PURCHASE,
            description="Test purchase",
        )
    )
    assert isinstance(result, int)

    transactions = transaction_repository.find_transactions([])
    assert len(transactions) == 1
    assert transactions[0].id == result
    assert transactions[0].account_id == 1
    assert transactions[0].security_key == "INF123"
    assert transactions[0].transaction_date == datetime.date(2024, 1, 1)
    assert transactions[0].units == Decimal(100)
    assert transactions[0].amount == Decimal(1000)
    assert transactions[0].type is TransactionType.PURCHASE
    assert transactions[0].description == "Test purchase"


def test_find_transactions_applies_filter_limit_and_offset(
    transaction_repository: SqliteTransactionRepository,
    security_repository: SqliteSecurityRepository,
    account_repository: SqliteAccountRepository,
) -> None:
    """Finding transactions applies key filter, limit, and offset correctly."""
    account_repository.insert_account(
        AccountCreate(name="Test Account", institution="Test Bank")
    )
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
                category=SecurityCategory.EQUITY,
                type=SecurityType.MUTUAL_FUND,
            ),
            SecurityCreate(
                key="CCC333",
                name="Gamma Fund",
                category=SecurityCategory.EQUITY,
                type=SecurityType.MUTUAL_FUND,
            ),
        ]
    )

    count = transaction_repository.insert_multiple_transactions(
        [
            TransactionCreate(
                account_id=1,
                security_key="AAA111",
                transaction_date=datetime.date(2024, 1, 1),
                units=Decimal(100),
                amount=Decimal(1000),
                type=TransactionType.PURCHASE,
                description="Test purchase",
            ),
            TransactionCreate(
                account_id=1,
                security_key="BBB222",
                transaction_date=datetime.date(2024, 1, 2),
                units=Decimal(200),
                amount=Decimal(2000),
                type=TransactionType.SALE,
                description="Test sale",
            ),
            TransactionCreate(
                account_id=1,
                security_key="CCC333",
                transaction_date=datetime.date(2024, 1, 3),
                units=Decimal(300),
                amount=Decimal(3000),
                type=TransactionType.PURCHASE,
                description="Test purchase 3",
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


def test_find_transactions_by_ids_returns_subset_and_empty_input_is_empty(
    transaction_repository: SqliteTransactionRepository,
    security_repository: SqliteSecurityRepository,
    account_repository: SqliteAccountRepository,
) -> None:
    """Finding transactions by IDs returns subset of matches and empty input returns empty."""
    security_repository.insert_security(
        SecurityCreate(
            key="AAA111",
            name="Alpha Fund",
            category=SecurityCategory.EQUITY,
            type=SecurityType.MUTUAL_FUND,
        )
    )
    account_repository.insert_account(
        AccountCreate(name="Test Account", institution="Test Bank")
    )
    count = transaction_repository.insert_multiple_transactions(
        [
            TransactionCreate(
                account_id=1,
                security_key="AAA111",
                transaction_date=datetime.date(2024, 1, 1),
                units=Decimal(100),
                amount=Decimal(1000),
                type=TransactionType.PURCHASE,
                description="Test purchase",
            ),
            TransactionCreate(
                account_id=1,
                security_key="AAA111",
                transaction_date=datetime.date(2024, 1, 2),
                units=Decimal(200),
                amount=Decimal(2000),
                type=TransactionType.SALE,
                description="Test sale",
            ),
            TransactionCreate(
                account_id=1,
                security_key="AAA111",
                transaction_date=datetime.date(2024, 1, 3),
                units=Decimal(300),
                amount=Decimal(3000),
                type=TransactionType.PURCHASE,
                description="Test purchase 3",
            ),
        ]
    )
    assert count == 3

    subset = transaction_repository.find_transactions_by_ids([1, 3])
    assert len(subset) == 2
    assert {t.id for t in subset} == {1, 3}

    empty = transaction_repository.find_transactions_by_ids([])
    assert len(empty) == 0


def test_delete_transaction_by_id_returns_true_then_false(
    transaction_repository: SqliteTransactionRepository,
    security_repository: SqliteSecurityRepository,
    account_repository: SqliteAccountRepository,
) -> None:
    """Deleting a transaction by ID returns True if deleted, then False if not found."""
    security_repository.insert_security(
        SecurityCreate(
            key="DEL123",
            name="Delete Me",
            category=SecurityCategory.EQUITY,
            type=SecurityType.MUTUAL_FUND,
        )
    )
    account_repository.insert_account(
        AccountCreate(name="Test Account", institution="Test Bank")
    )
    transaction_repository.insert_transaction(
        TransactionCreate(
            account_id=1,
            security_key="DEL123",
            transaction_date=datetime.date(2024, 1, 1),
            units=Decimal(100),
            amount=Decimal(1000),
            type=TransactionType.PURCHASE,
            description="Test purchase",
        )
    )
    first_delete = transaction_repository.delete_transaction_by_id(1)
    assert first_delete is True

    second_delete = transaction_repository.delete_transaction_by_id(1)
    assert second_delete is False

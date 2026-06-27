"""SQLite transaction repository unit tests."""

import datetime
from decimal import Decimal

import pytest

from niveshpy.domain.query.ast import Field, FilterNode, Operator
from niveshpy.infrastructure.sqlite.repositories import (
    SqliteAccountRepository,
    SqliteSecurityRepository,
    SqliteTransactionRepository,
)
from niveshpy.models.account import AccountCreate
from niveshpy.models.security import SecurityCategory, SecurityCreate, SecurityType
from niveshpy.models.transaction import TransactionCreate, TransactionType


@pytest.fixture(scope="function")
def account_repository(db):
    """Provide a fresh SqliteAccountRepository for each test."""
    return SqliteAccountRepository(db)


@pytest.fixture(scope="function")
def security_repository(db):
    """Provide a fresh SqliteSecurityRepository for each test."""
    return SqliteSecurityRepository(db)


@pytest.fixture(scope="function")
def transaction_repository(db, account_repository, security_repository):
    """Provide a fresh SqliteTransactionRepository for each test."""
    return SqliteTransactionRepository(db, account_repository, security_repository)


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

    filtered = transaction_repository.find_transactions(
        [FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "B")]
    )
    assert len(filtered) == 1
    assert filtered[0].security_key == "BBB222"

    paged = transaction_repository.find_transactions([], limit=1, offset=1)
    assert len(paged) == 1
    assert paged[0].security_key == "BBB222"


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


class TestFindTransactionsIsIgnored:
    """Tests for the is_ignored flag handling in find_transactions."""

    def test_excluded_by_default(
        self,
        transaction_repository: SqliteTransactionRepository,
        security_repository: SqliteSecurityRepository,
        account_repository: SqliteAccountRepository,
    ) -> None:
        """Ignored transactions are excluded by default."""
        account_repository.insert_account(
            AccountCreate(name="Test Account", institution="Test Bank")
        )
        security_repository.insert_security(
            SecurityCreate(
                key="IGN123",
                name="Ignored Fund",
                category=SecurityCategory.EQUITY,
                type=SecurityType.MUTUAL_FUND,
            )
        )

        # Insert one normal and one ignored transaction
        transaction_repository.insert_transaction(
            TransactionCreate(
                account_id=1,
                security_key="IGN123",
                transaction_date=datetime.date(2024, 1, 1),
                units=Decimal(100),
                amount=Decimal(1000),
                type=TransactionType.PURCHASE,
                description="Normal transaction",
                is_ignored=False,
            )
        )
        transaction_repository.insert_transaction(
            TransactionCreate(
                account_id=1,
                security_key="IGN123",
                transaction_date=datetime.date(2024, 1, 2),
                units=Decimal(200),
                amount=Decimal(2000),
                type=TransactionType.PURCHASE,
                description="Ignored transaction",
                is_ignored=True,
            )
        )

        # With default include_ignored=False, only normal should be returned
        result = transaction_repository.find_transactions([], include_ignored=False)
        assert len(result) == 1
        assert result[0].description == "Normal transaction"
        assert result[0].is_ignored is False

    def test_included_with_flag(
        self,
        transaction_repository: SqliteTransactionRepository,
        security_repository: SqliteSecurityRepository,
        account_repository: SqliteAccountRepository,
    ) -> None:
        """Ignored transactions are included when include_ignored=True."""
        account_repository.insert_account(
            AccountCreate(name="Test Account", institution="Test Bank")
        )
        security_repository.insert_security(
            SecurityCreate(
                key="IGN123",
                name="Ignored Fund",
                category=SecurityCategory.EQUITY,
                type=SecurityType.MUTUAL_FUND,
            )
        )

        # Insert one normal and one ignored transaction
        transaction_repository.insert_transaction(
            TransactionCreate(
                account_id=1,
                security_key="IGN123",
                transaction_date=datetime.date(2024, 1, 1),
                units=Decimal(100),
                amount=Decimal(1000),
                type=TransactionType.PURCHASE,
                description="Normal transaction",
                is_ignored=False,
            )
        )
        transaction_repository.insert_transaction(
            TransactionCreate(
                account_id=1,
                security_key="IGN123",
                transaction_date=datetime.date(2024, 1, 2),
                units=Decimal(200),
                amount=Decimal(2000),
                type=TransactionType.PURCHASE,
                description="Ignored transaction",
                is_ignored=True,
            )
        )

        # With include_ignored=True, both should be returned
        result = transaction_repository.find_transactions([], include_ignored=True)
        assert len(result) == 2
        descriptions = {txn.description for txn in result}
        assert "Normal transaction" in descriptions
        assert "Ignored transaction" in descriptions

    def test_find_holding_units_excludes_ignored(
        self,
        transaction_repository: SqliteTransactionRepository,
        security_repository: SqliteSecurityRepository,
        account_repository: SqliteAccountRepository,
    ) -> None:
        """find_holding_units excludes ignored transactions."""
        account_repository.insert_account(
            AccountCreate(name="Test Account", institution="Test Bank")
        )
        security_repository.insert_security(
            SecurityCreate(
                key="HLD123",
                name="Holdings Fund",
                category=SecurityCategory.EQUITY,
                type=SecurityType.MUTUAL_FUND,
            )
        )

        # Insert a normal transaction and an ignored transaction
        transaction_repository.insert_transaction(
            TransactionCreate(
                account_id=1,
                security_key="HLD123",
                transaction_date=datetime.date(2024, 1, 1),
                units=Decimal(100),
                amount=Decimal(1000),
                type=TransactionType.PURCHASE,
                description="Normal purchase",
                is_ignored=False,
            )
        )
        transaction_repository.insert_transaction(
            TransactionCreate(
                account_id=1,
                security_key="HLD123",
                transaction_date=datetime.date(2024, 1, 2),
                units=Decimal(200),
                amount=Decimal(2000),
                type=TransactionType.PURCHASE,
                description="Ignored purchase",
                is_ignored=True,
            )
        )

        # find_holding_units should only count the normal transaction (excludes ignored)
        holdings = transaction_repository.find_holding_units([])
        # Filter to get only the holding for account 1 and security HLD123
        holding_row = next(
            (h for h in holdings if h.account_id == 1 and h.security_key == "HLD123"),
            None,
        )
        assert holding_row is not None
        # Should only include the 100 units from the normal transaction, not the 200 from ignored
        assert holding_row.total_units == Decimal(100)

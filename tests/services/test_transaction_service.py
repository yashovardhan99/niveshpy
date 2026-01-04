"""Tests for TransactionService."""

import datetime
from collections.abc import Generator, Sequence
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlmodel import Session

from niveshpy.exceptions import (
    AmbiguousResourceError,
    InvalidInputError,
    ResourceNotFoundError,
)
from niveshpy.models.account import Account
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.models.transaction import Transaction, TransactionDisplay, TransactionType
from niveshpy.services.transaction import TransactionService


@pytest.fixture
def transaction_service(session: Session) -> Generator[TransactionService, None, None]:
    """Create TransactionService instance with patched get_session."""
    with patch("niveshpy.services.transaction.get_session") as mock_get_session:
        # Make get_session return a context manager that yields the test session
        mock_get_session.return_value.__enter__.return_value = session
        mock_get_session.return_value.__exit__.return_value = None
        yield TransactionService()


@pytest.fixture
def sample_accounts(session: Session) -> Sequence[Account]:
    """Create sample accounts for testing."""
    accounts = [
        Account(name="Savings", institution="HDFC Bank"),
        Account(name="Investment", institution="ICICI"),
        Account(name="Pension", institution="SBI"),
    ]
    session.add_all(accounts)
    session.commit()
    for account in accounts:
        session.refresh(account)
    return accounts


@pytest.fixture
def sample_securities(session: Session) -> Sequence[Security]:
    """Create sample securities for testing."""
    securities = [
        Security(
            key="123456",
            name="HDFC Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        ),
        Security(
            key="234567",
            name="ICICI Liquid Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.DEBT,
        ),
        Security(
            key="RELI",
            name="Reliance Industries",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        ),
    ]
    session.add_all(securities)
    session.commit()
    for security in securities:
        session.refresh(security)
    return securities


@pytest.fixture
def sample_transactions(
    session: Session,
    sample_accounts: Sequence[Account],
    sample_securities: Sequence[Security],
) -> Sequence[Transaction]:
    """Create sample transactions for testing."""
    transactions = [
        Transaction(
            transaction_date=datetime.date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Purchase HDFC Fund",
            amount=Decimal("10000.00"),
            units=Decimal("100.50"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
        Transaction(
            transaction_date=datetime.date(2024, 2, 20),
            type=TransactionType.SALE,
            description="Sold ICICI Fund",
            amount=Decimal("5000.00"),
            units=Decimal("50.25"),
            account_id=sample_accounts[1].id,
            security_key=sample_securities[1].key,
        ),
        Transaction(
            transaction_date=datetime.date(2024, 3, 10),
            type=TransactionType.PURCHASE,
            description="Dividend from Reliance",
            amount=Decimal("500.00"),
            units=Decimal("0.00"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[2].key,
        ),
        Transaction(
            transaction_date=datetime.date(2024, 4, 5),
            type=TransactionType.PURCHASE,
            description="Additional purchase HDFC",
            amount=Decimal("20000.00"),
            units=Decimal("200.75"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
    ]
    session.add_all(transactions)
    session.commit()
    for transaction in transactions:
        session.refresh(transaction)
    return transactions


class TestListTransactions:
    """Tests for list_transactions method."""

    def test_list_all_transactions_no_filter(
        self, transaction_service, sample_transactions
    ):
        """Test listing all transactions without any filters."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0
        )

        assert len(transactions) == 4
        assert all(hasattr(txn, "security") for txn in transactions)
        assert all(hasattr(txn, "account") for txn in transactions)

    def test_list_transactions_with_limit(
        self, transaction_service, sample_transactions
    ):
        """Test listing transactions with limit."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=2, offset=0
        )

        assert len(transactions) == 2

    def test_list_transactions_with_offset(
        self, transaction_service, sample_transactions
    ):
        """Test listing transactions with offset."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=2
        )

        assert len(transactions) == 2

    def test_list_transactions_with_limit_and_offset(
        self, transaction_service, sample_transactions
    ):
        """Test listing transactions with both limit and offset."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=2, offset=1
        )

        assert len(transactions) == 2

    def test_list_transactions_offset_beyond_total(
        self, transaction_service, sample_transactions
    ):
        """Test listing transactions with offset beyond total count."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=10
        )

        assert len(transactions) == 0

    def test_list_transactions_with_query_filter(
        self, transaction_service, sample_transactions
    ):
        """Test listing transactions with query filter (matches security)."""
        transactions = transaction_service.list_transactions(
            queries=("HDFC",), limit=30, offset=0
        )

        assert len(transactions) >= 1
        # Default query matches security fields, not description
        assert any("HDFC" in txn.security.name for txn in transactions)

    def test_list_transactions_query_no_matches(
        self, transaction_service, sample_transactions
    ):
        """Test listing transactions with query that has no matches."""
        transactions = transaction_service.list_transactions(
            queries=("NonExistentTransaction",), limit=30, offset=0
        )

        assert len(transactions) == 0

    def test_list_transactions_empty_database(self, transaction_service):
        """Test listing transactions when database is empty."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0
        )

        assert len(transactions) == 0

    def test_list_transactions_invalid_limit_zero(
        self, transaction_service, sample_transactions
    ):
        """Test that zero limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be positive"):
            transaction_service.list_transactions(queries=(), limit=0, offset=0)

    def test_list_transactions_invalid_limit_negative(
        self, transaction_service, sample_transactions
    ):
        """Test that negative limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be positive"):
            transaction_service.list_transactions(queries=(), limit=-1, offset=0)

    def test_list_transactions_invalid_offset_negative(
        self, transaction_service, sample_transactions
    ):
        """Test that negative offset raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Offset cannot be negative"):
            transaction_service.list_transactions(queries=(), limit=30, offset=-1)

    def test_list_transactions_returns_with_relations(
        self, transaction_service, sample_transactions
    ):
        """Test that list_transactions returns transactions with related objects."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0
        )

        assert len(transactions) > 0
        # Check that security and account are populated
        assert transactions[0].security.key is not None
        assert transactions[0].account.id is not None


class TestAddTransaction:
    """Tests for add_transaction method."""

    def test_add_transaction_success(
        self, transaction_service, sample_accounts, sample_securities, session
    ):
        """Test successfully adding a new transaction."""
        result = transaction_service.add_transaction(
            transaction_date=datetime.date(2024, 5, 1),
            transaction_type=TransactionType.PURCHASE,
            description="New purchase",
            amount=Decimal("15000.00"),
            units=Decimal("150.00"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
            source=None,
        )

        assert isinstance(result, Transaction)
        assert result.id is not None
        assert result.transaction_date == datetime.date(2024, 5, 1)
        assert result.type == TransactionType.PURCHASE
        assert result.description == "New purchase"
        assert result.amount == Decimal("15000.00")
        assert result.units == Decimal("150.00")
        assert result.account_id == sample_accounts[0].id
        assert result.security_key == sample_securities[0].key
        assert result.properties == {}

    def test_add_transaction_with_source(
        self, transaction_service, sample_accounts, sample_securities, session
    ):
        """Test adding transaction with source property."""
        result = transaction_service.add_transaction(
            transaction_date=datetime.date(2024, 5, 1),
            transaction_type=TransactionType.PURCHASE,
            description="New purchase",
            amount=Decimal("15000.00"),
            units=Decimal("150.00"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
            source="CAS",
        )

        assert result.properties == {"source": "CAS"}

    def test_add_transaction_invalid_account_id(
        self, transaction_service, sample_securities, session
    ):
        """Test that invalid account_id raises ResourceNotFoundError."""
        with pytest.raises(ResourceNotFoundError, match="Account.*99999"):
            transaction_service.add_transaction(
                transaction_date=datetime.date(2024, 5, 1),
                transaction_type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("1000.00"),
                units=Decimal("10.00"),
                account_id=99999,
                security_key=sample_securities[0].key,
                source=None,
            )

    def test_add_transaction_invalid_security_key(
        self, transaction_service, sample_accounts, session
    ):
        """Test that invalid security_key raises ResourceNotFoundError."""
        with pytest.raises(ResourceNotFoundError, match="Security.*INVALID"):
            transaction_service.add_transaction(
                transaction_date=datetime.date(2024, 5, 1),
                transaction_type=TransactionType.PURCHASE,
                description="Test",
                amount=Decimal("1000.00"),
                units=Decimal("10.00"),
                account_id=sample_accounts[0].id,
                security_key="INVALID",
                source=None,
            )

    def test_add_transaction_all_transaction_types(
        self, transaction_service, sample_accounts, sample_securities, session
    ):
        """Test adding transactions with all TransactionType values."""
        for idx, txn_type in enumerate(TransactionType):
            result = transaction_service.add_transaction(
                transaction_date=datetime.date(2024, 5, idx + 1),
                transaction_type=txn_type,
                description=f"Test {txn_type.value}",
                amount=Decimal("1000.00"),
                units=Decimal("10.00"),
                account_id=sample_accounts[0].id,
                security_key=sample_securities[0].key,
                source=None,
            )
            assert result.type == txn_type

    def test_add_transaction_zero_amount(
        self, transaction_service, sample_accounts, sample_securities, session
    ):
        """Test adding transaction with zero amount."""
        result = transaction_service.add_transaction(
            transaction_date=datetime.date(2024, 5, 1),
            transaction_type=TransactionType.PURCHASE,
            description="Zero amount",
            amount=Decimal("0.00"),
            units=Decimal("0.00"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
            source=None,
        )

        assert result.amount == Decimal("0.00")
        assert result.units == Decimal("0.00")

    def test_add_transaction_large_amounts(
        self, transaction_service, sample_accounts, sample_securities, session
    ):
        """Test adding transaction with large decimal values."""
        result = transaction_service.add_transaction(
            transaction_date=datetime.date(2024, 5, 1),
            transaction_type=TransactionType.PURCHASE,
            description="Large amount",
            amount=Decimal("99999999.99"),
            units=Decimal("12345678.123"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
            source=None,
        )

        assert result.amount == Decimal("99999999.99")
        assert result.units == Decimal("12345678.123")

    def test_add_transaction_unicode_description(
        self, transaction_service, sample_accounts, sample_securities, session
    ):
        """Test adding transaction with unicode characters in description."""
        result = transaction_service.add_transaction(
            transaction_date=datetime.date(2024, 5, 1),
            transaction_type=TransactionType.PURCHASE,
            description="म्यूचुअल फंड खरीदा",
            amount=Decimal("1000.00"),
            units=Decimal("10.00"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
            source=None,
        )

        assert result.description == "म्यूचुअल फंड खरीदा"


class TestGetAccountChoices:
    """Tests for get_account_choices method."""

    def test_get_account_choices_returns_list(
        self, transaction_service, sample_accounts
    ):
        """Test that get_account_choices returns a list of dicts."""
        choices = transaction_service.get_account_choices()

        assert isinstance(choices, list)
        assert len(choices) == 3
        assert all(isinstance(choice, dict) for choice in choices)

    def test_get_account_choices_structure(self, transaction_service, sample_accounts):
        """Test the structure of account choices."""
        choices = transaction_service.get_account_choices()

        for choice in choices:
            assert "value" in choice
            assert "name" in choice
            assert isinstance(choice["value"], str)
            assert isinstance(choice["name"], str)

    def test_get_account_choices_empty_database(self, transaction_service):
        """Test get_account_choices with empty database."""
        choices = transaction_service.get_account_choices()

        assert choices == []

    def test_get_account_choices_format(self, transaction_service, sample_accounts):
        """Test that account choices are formatted correctly."""
        choices = transaction_service.get_account_choices()

        # Check first choice format
        first_choice = choices[0]
        account_id = int(first_choice["value"])
        assert account_id in [acc.id for acc in sample_accounts]
        assert ":" in first_choice["name"]
        assert "(" in first_choice["name"]


class TestGetSecurityChoices:
    """Tests for get_security_choices method."""

    def test_get_security_choices_returns_list(
        self, transaction_service, sample_securities
    ):
        """Test that get_security_choices returns a list of dicts."""
        choices = transaction_service.get_security_choices()

        assert isinstance(choices, list)
        assert len(choices) == 3
        assert all(isinstance(choice, dict) for choice in choices)

    def test_get_security_choices_structure(
        self, transaction_service, sample_securities
    ):
        """Test the structure of security choices."""
        choices = transaction_service.get_security_choices()

        for choice in choices:
            assert "value" in choice
            assert "name" in choice
            assert isinstance(choice["value"], str)
            assert isinstance(choice["name"], str)

    def test_get_security_choices_empty_database(self, transaction_service):
        """Test get_security_choices with empty database."""
        choices = transaction_service.get_security_choices()

        assert choices == []

    def test_get_security_choices_format(self, transaction_service, sample_securities):
        """Test that security choices are formatted correctly."""
        choices = transaction_service.get_security_choices()

        # Check first choice format
        first_choice = choices[0]
        assert first_choice["value"] in [sec.key for sec in sample_securities]
        assert "(" in first_choice["name"]
        assert first_choice["value"] in first_choice["name"]


class TestResolveTransaction:
    """Tests for resolve_transaction method."""

    def test_resolve_empty_queries_ambiguous_allowed(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test resolving with empty queries when ambiguous is allowed."""
        candidates: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=(), limit=10, allow_ambiguous=True
            )
        )

        assert len(candidates) == 4

    def test_resolve_empty_queries_ambiguous_not_allowed(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test resolving with empty queries when ambiguous is not allowed."""
        with pytest.raises(InvalidInputError, match="No queries provided"):
            transaction_service.resolve_transaction(
                queries=(), limit=10, allow_ambiguous=False
            )

    def test_resolve_empty_queries_respects_limit(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test that empty queries resolution respects limit."""
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=(), limit=2, allow_ambiguous=True
            )
        )

        assert len(resolution) == 2

    def test_resolve_exact_match_by_id(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test resolving by exact transaction id."""
        transaction_id = sample_transactions[0].id
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=(str(transaction_id),), limit=10, allow_ambiguous=True
            )
        )

        assert len(resolution) == 1
        assert resolution[0].id == transaction_id

    def test_resolve_exact_match_by_id_with_whitespace(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test resolving by id with surrounding whitespace."""
        transaction_id = sample_transactions[0].id
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=(f"  {transaction_id}  ",), limit=10, allow_ambiguous=True
            )
        )

        assert len(resolution) == 1
        assert resolution[0].id == transaction_id

    def test_resolve_nonexistent_id_ambiguous_not_allowed(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test resolving non-existent id when ambiguous not allowed."""
        with pytest.raises(AmbiguousResourceError, match="Transaction.*99999"):
            transaction_service.resolve_transaction(
                queries=("99999",), limit=10, allow_ambiguous=False
            )

    def test_resolve_nonexistent_id_ambiguous_allowed(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test resolving non-existent id when ambiguous allowed falls back to text search."""
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=("99999",), limit=10, allow_ambiguous=True
            )
        )

        # Should fall back to text search and find nothing
        assert len(resolution) == 0

    def test_resolve_text_search_no_matches(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test text search with no matches."""
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=("NonExistentTransaction",), limit=10, allow_ambiguous=True
            )
        )

        assert len(resolution) == 0

    def test_resolve_text_search_single_match(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test text search with exactly one match (matches security)."""
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=("Reliance",), limit=10, allow_ambiguous=True
            )
        )

        assert len(resolution) == 1
        assert "Reliance" in resolution[0].security

    def test_resolve_text_search_multiple_matches(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test text search with multiple matches (security)."""
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=("Fund",), limit=10, allow_ambiguous=True
            )
        )

        assert len(resolution) >= 2
        # security is a formatted string like "name (key)"
        assert all("Fund" in txn.security for txn in resolution)

    def test_resolve_text_search_multiple_matches_ambiguous_not_allowed(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test text search with multiple matches when ambiguous not allowed."""
        with pytest.raises(AmbiguousResourceError, match="Transaction.*Fund"):
            transaction_service.resolve_transaction(
                queries=("Fund",), limit=10, allow_ambiguous=False
            )

    def test_resolve_text_search_respects_limit(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test that text search respects limit parameter."""
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=("Fund",), limit=1, allow_ambiguous=True
            )
        )

        # With limit=1 and exactly 1 result, it should return that one result
        assert len(resolution) == 1

    def test_resolve_non_numeric_query_ambiguous_not_allowed(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test that non-numeric query with ambiguous not allowed."""
        with pytest.raises(AmbiguousResourceError, match="Transaction.*Fund"):
            transaction_service.resolve_transaction(
                queries=("Fund",), limit=10, allow_ambiguous=False
            )

    def test_resolve_empty_database(self, transaction_service: TransactionService):
        """Test resolving in empty database."""
        resolution: Sequence[TransactionDisplay] = (
            transaction_service.resolve_transaction(
                queries=("test",), limit=10, allow_ambiguous=True
            )
        )

        assert len(resolution) == 0


class TestDeleteTransaction:
    """Tests for delete_transaction method."""

    def test_delete_transaction_success(self, transaction_service, sample_transactions):
        """Test successfully deleting a transaction."""
        transaction_id = sample_transactions[0].id
        result = transaction_service.delete_transaction(transaction_id)

        assert result is True

        # Verify transaction is deleted
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0
        )
        assert len(transactions) == 3
        assert not any(txn.id == transaction_id for txn in transactions)

    def test_delete_transaction_nonexistent(
        self, transaction_service, sample_transactions
    ):
        """Test deleting non-existent transaction returns False."""
        result = transaction_service.delete_transaction(99999)

        assert result is False

    def test_delete_transaction_twice(self, transaction_service, sample_transactions):
        """Test deleting same transaction twice."""
        transaction_id = sample_transactions[0].id

        # First deletion should succeed
        result1 = transaction_service.delete_transaction(transaction_id)
        assert result1 is True

        # Second deletion should fail
        result2 = transaction_service.delete_transaction(transaction_id)
        assert result2 is False

    def test_delete_all_transactions(self, transaction_service, sample_transactions):
        """Test deleting all transactions."""
        for transaction in sample_transactions:
            result = transaction_service.delete_transaction(transaction.id)
            assert result is True

        # Verify all deleted
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0
        )
        assert len(transactions) == 0

    def test_delete_transaction_does_not_affect_others(
        self, transaction_service, sample_transactions
    ):
        """Test that deleting one transaction doesn't affect others."""
        transaction_to_delete = sample_transactions[2]
        initial_count = len(sample_transactions)

        result = transaction_service.delete_transaction(transaction_to_delete.id)
        assert result is True

        # Verify only one transaction deleted
        remaining_transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0
        )
        assert len(remaining_transactions) == initial_count - 1
        assert not any(
            txn.id == transaction_to_delete.id for txn in remaining_transactions
        )

    def test_delete_transaction_does_not_cascade_to_account(
        self, transaction_service, sample_transactions, sample_accounts, session
    ):
        """Test that deleting a transaction doesn't delete the related account."""
        transaction_id = sample_transactions[0].id
        account_id = sample_transactions[0].account_id

        result = transaction_service.delete_transaction(transaction_id)
        assert result is True

        # Verify account still exists
        account = session.get(Account, account_id)
        assert account is not None

    def test_delete_transaction_does_not_cascade_to_security(
        self, transaction_service, sample_transactions, sample_securities, session
    ):
        """Test that deleting a transaction doesn't delete the related security."""
        transaction_id = sample_transactions[0].id
        security_key = sample_transactions[0].security_key

        result = transaction_service.delete_transaction(transaction_id)
        assert result is True

        # Verify security still exists
        security = session.get(Security, security_key)
        assert security is not None

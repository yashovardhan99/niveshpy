"""Tests for TransactionService."""

import datetime
from collections.abc import Sequence
from decimal import Decimal
from unittest.mock import patch

import pytest

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.domain.repositories import AccountRepository, SecurityRepository
from niveshpy.domain.services import LotAccountingService
from niveshpy.exceptions import (
    AmbiguousResourceError,
    InvalidInputError,
    ResourceNotFoundError,
)
from niveshpy.models.account import AccountCreate, AccountPublic
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.models.transaction import (
    Transaction,
    TransactionCreate,
    TransactionPublicWithRelations,
    TransactionPublicWithRelationsAndCost,
    TransactionType,
)
from niveshpy.services.transaction import TransactionService
from tests.services.conftest import (
    MockAccountRepository,
    MockSecurityRepository,
    MockTransactionRepository,
)


@pytest.fixture
def account_repository() -> MockAccountRepository:
    """Fixture for MockAccountRepository."""
    return MockAccountRepository()


@pytest.fixture
def security_repository() -> MockSecurityRepository:
    """Fixture for MockSecurityRepository."""
    return MockSecurityRepository()


@pytest.fixture
def transaction_service(
    account_repository: MockAccountRepository,
    security_repository: MockSecurityRepository,
) -> TransactionService:
    """Create TransactionService instance with the mocked repositories."""
    transaction_repo = MockTransactionRepository(
        account_repository=account_repository, security_repository=security_repository
    )
    return TransactionService(
        transaction_repository=transaction_repo,
        account_repository=account_repository,
        security_repository=security_repository,
        lot_accounting_service=LotAccountingService(),
    )


@pytest.fixture
def sample_accounts(
    account_repository: MockAccountRepository,
) -> Sequence[AccountPublic]:
    """Create sample accounts for testing."""
    accounts = [
        AccountCreate(name="Savings", institution="HDFC Bank"),
        AccountCreate(name="Investment", institution="ICICI"),
        AccountCreate(name="Pension", institution="SBI"),
    ]
    account_repository.insert_multiple_accounts(accounts)
    return account_repository.find_accounts([])


@pytest.fixture
def sample_securities(
    security_repository: MockSecurityRepository,
) -> Sequence[Security]:
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
    security_repository.insert_multiple_securities(securities)
    return security_repository.find_securities([])


@pytest.fixture
def sample_transactions(
    sample_accounts: Sequence[AccountPublic],
    sample_securities: Sequence[Security],
    transaction_service: TransactionService,
) -> Sequence[Transaction]:
    """Create sample transactions for testing."""
    transactions = [
        TransactionCreate(
            transaction_date=datetime.date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Purchase HDFC Fund",
            amount=Decimal("10000.00"),
            units=Decimal("100.50"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
        TransactionCreate(
            transaction_date=datetime.date(2024, 2, 20),
            type=TransactionType.SALE,
            description="Sold ICICI Fund",
            amount=Decimal("5000.00"),
            units=Decimal("50.25"),
            account_id=sample_accounts[1].id,
            security_key=sample_securities[1].key,
        ),
        TransactionCreate(
            transaction_date=datetime.date(2024, 3, 10),
            type=TransactionType.PURCHASE,
            description="Dividend from Reliance",
            amount=Decimal("500.00"),
            units=Decimal("0.00"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[2].key,
        ),
        TransactionCreate(
            transaction_date=datetime.date(2024, 4, 5),
            type=TransactionType.PURCHASE,
            description="Additional purchase HDFC",
            amount=Decimal("20000.00"),
            units=Decimal("200.75"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
    ]
    transaction_service.transaction_repository.insert_multiple_transactions(
        transactions
    )
    return transaction_service.transaction_repository.find_transactions([])


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
        with patch.object(
            transaction_service.transaction_repository, "find_transactions"
        ) as mock_find:
            # Call the method to ensure the mock is used
            transaction_service.list_transactions(queries=("HDFC",), limit=30, offset=0)
            # Check that the repository's find_transactions was called with correct filters
            mock_find.assert_called_once()
            assert mock_find.call_args[0][0] == [
                FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "HDFC")
            ]

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


@pytest.fixture
def cost_basis_transactions(
    sample_accounts: Sequence[AccountPublic],
    sample_securities: Sequence[Security],
    transaction_service: TransactionService,
) -> Sequence[Transaction]:
    """Create transactions with proper buy-before-sell ordering for cost basis tests."""
    transactions = [
        TransactionCreate(
            transaction_date=datetime.date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Purchase HDFC Fund",
            amount=Decimal("10000.00"),
            units=Decimal("100.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
        TransactionCreate(
            transaction_date=datetime.date(2024, 2, 20),
            type=TransactionType.PURCHASE,
            description="Purchase HDFC Fund again",
            amount=Decimal("15000.00"),
            units=Decimal("150.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
        TransactionCreate(
            transaction_date=datetime.date(2024, 3, 10),
            type=TransactionType.SALE,
            description="Sell HDFC Fund",
            amount=Decimal("12000.00"),
            units=Decimal("-120.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
    ]
    transaction_service.transaction_repository.insert_multiple_transactions(
        transactions
    )
    return transaction_service.transaction_repository.find_transactions([])


class TestListTransactionsWithCost:
    """Tests for list_transactions with cost=True."""

    def test_list_with_cost_returns_cost_models(
        self, transaction_service, cost_basis_transactions
    ):
        """Test that cost=True returns TransactionPublicWithRelationsAndCost."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0, cost=True
        )

        assert len(transactions) == 3
        assert all(
            isinstance(t, TransactionPublicWithRelationsAndCost) for t in transactions
        )

    def test_purchase_transactions_have_no_cost(
        self, transaction_service, cost_basis_transactions
    ):
        """Test that purchase transactions have cost=None."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0, cost=True
        )

        purchases = [t for t in transactions if t.type == TransactionType.PURCHASE]
        assert len(purchases) == 2
        assert all(t.cost is None for t in purchases)

    def test_sale_transaction_has_fifo_cost(
        self, transaction_service, cost_basis_transactions
    ):
        """Test that sale transaction has FIFO-computed cost basis."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0, cost=True
        )

        sales = [t for t in transactions if t.type == TransactionType.SALE]
        assert len(sales) == 1
        # FIFO: 100 units from lot 1 (10000) + 20 from lot 2 (15000 * 20/150 = 2000)
        assert sales[0].cost == Decimal("12000.00")

    def test_cost_with_query_filter(self, transaction_service, cost_basis_transactions):
        """Test cost computation works with query filters."""
        with patch.object(
            transaction_service.transaction_repository, "find_transactions"
        ) as mock_find:
            transaction_service.list_transactions(
                queries=("HDFC", "type:sale"), limit=30, offset=0, cost=True
            )
            mock_find.assert_called()
            # Cost-basis computation should only use security and account filters
            assert mock_find.call_args_list[0][0][0] == [
                FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "HDFC")
            ]
            # Normal filters should still be passed for the main query
            assert mock_find.call_args_list[1][0][0] == [
                FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "HDFC"),
                FilterNode(Field.TYPE, Operator.REGEX_MATCH, "sale"),
            ]

    def test_cost_with_limit(self, transaction_service, cost_basis_transactions):
        """Test cost computation works with limit."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=1, offset=0, cost=True
        )

        assert len(transactions) == 1
        assert isinstance(transactions[0], TransactionPublicWithRelationsAndCost)

    def test_cost_preserves_relations(
        self, transaction_service, cost_basis_transactions
    ):
        """Test that cost=True results still include security and account relations."""
        transactions = transaction_service.list_transactions(
            queries=(), limit=30, offset=0, cost=True
        )

        assert len(transactions) > 0
        assert transactions[0].security.key is not None
        assert transactions[0].account.id is not None


class TestAddTransaction:
    """Tests for add_transaction method."""

    def test_add_transaction_success(
        self, transaction_service, sample_accounts, sample_securities
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

        assert isinstance(result, int)
        check_transaction = (
            transaction_service.transaction_repository.get_transaction_by_id(result)
        )
        assert check_transaction.id is not None
        assert check_transaction.transaction_date == datetime.date(2024, 5, 1)
        assert check_transaction.type == TransactionType.PURCHASE
        assert check_transaction.description == "New purchase"
        assert check_transaction.amount == Decimal("15000.00")
        assert check_transaction.units == Decimal("150.00")
        assert check_transaction.account_id == sample_accounts[0].id
        assert check_transaction.security_key == sample_securities[0].key
        assert check_transaction.properties == {}

    def test_add_transaction_with_source(
        self, transaction_service, sample_accounts, sample_securities
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

        check_transaction = (
            transaction_service.transaction_repository.get_transaction_by_id(result)
        )

        assert check_transaction.properties == {"source": "CAS"}

    def test_add_transaction_invalid_account_id(
        self, transaction_service, sample_securities
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
        self, transaction_service, sample_accounts
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
        self, transaction_service, sample_accounts, sample_securities
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
            check_transaction = (
                transaction_service.transaction_repository.get_transaction_by_id(result)
            )

            assert check_transaction.type == txn_type

    def test_add_transaction_zero_amount(
        self, transaction_service, sample_accounts, sample_securities
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

        check_transaction = (
            transaction_service.transaction_repository.get_transaction_by_id(result)
        )

        assert check_transaction.amount == Decimal("0.00")
        assert check_transaction.units == Decimal("0.00")

    def test_add_transaction_large_amounts(
        self, transaction_service, sample_accounts, sample_securities
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

        check_transaction = (
            transaction_service.transaction_repository.get_transaction_by_id(result)
        )

        assert check_transaction.amount == Decimal("99999999.99")
        assert check_transaction.units == Decimal("12345678.123")

    def test_add_transaction_unicode_description(
        self, transaction_service, sample_accounts, sample_securities
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

        check_transaction = (
            transaction_service.transaction_repository.get_transaction_by_id(result)
        )

        assert check_transaction.description == "म्यूचुअल फंड खरीदा"


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
        candidates: Sequence[TransactionPublicWithRelations] = (
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
        resolution: Sequence[TransactionPublicWithRelations] = (
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
        resolution: Sequence[TransactionPublicWithRelations] = (
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
        resolution: Sequence[TransactionPublicWithRelations] = (
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
        with patch.object(
            transaction_service.transaction_repository, "find_transactions"
        ) as mock_find:
            mock_find.return_value = []
            resolution: Sequence[TransactionPublicWithRelations] = (
                transaction_service.resolve_transaction(
                    queries=("99999",), limit=10, allow_ambiguous=True
                )
            )
            mock_find.assert_called_once()

        # Should fall back to text search and find nothing
        assert len(resolution) == 0

    def test_resolve_text_search_no_matches(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test text search with no matches."""
        with patch.object(
            transaction_service.transaction_repository, "find_transactions"
        ) as mock_find:
            mock_find.return_value = []
            resolution: Sequence[TransactionPublicWithRelations] = (
                transaction_service.resolve_transaction(
                    queries=("NonExistentTransaction",), limit=10, allow_ambiguous=True
                )
            )
            mock_find.assert_called_once()

        assert len(resolution) == 0

    def test_resolve_text_search_single_match(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test text search with exactly one match (matches security)."""
        with patch.object(
            transaction_service.transaction_repository, "find_transactions"
        ) as mock_find:
            # Ensure the mock is used and returns the expected result
            mock_find.return_value = [
                txn for txn in sample_transactions if "Reliance" in txn.security.name
            ]
            resolution: Sequence[TransactionPublicWithRelations] = (
                transaction_service.resolve_transaction(
                    queries=("Reliance",), limit=10, allow_ambiguous=True
                )
            )

            assert len(resolution) == 1
            assert "Reliance" in resolution[0].security.name

    def test_resolve_text_search_multiple_matches(
        self,
        transaction_service: TransactionService,
        sample_transactions: Sequence[Transaction],
    ):
        """Test text search with multiple matches (security)."""
        with patch.object(
            transaction_service.transaction_repository, "find_transactions"
        ) as mock_find:
            # Ensure the mock is used and returns the expected results
            mock_find.return_value = [
                txn for txn in sample_transactions if "Fund" in txn.security.name
            ]
            resolution: Sequence[TransactionPublicWithRelations] = (
                transaction_service.resolve_transaction(
                    queries=("Fund",), limit=10, allow_ambiguous=True
                )
            )
            mock_find.assert_called_once()

            assert len(resolution) >= 2
            # security is a formatted string like "name (key)"
            assert all("Fund" in txn.security.name for txn in resolution)

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
        with patch.object(
            transaction_service.transaction_repository, "find_transactions"
        ) as mock_find:
            # Ensure the mock is used and returns the expected results
            transaction_service.resolve_transaction(
                queries=("Fund",), limit=1, allow_ambiguous=True
            )
            assert mock_find.call_args[1]["limit"] == 1
            mock_find.assert_called_once()

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
        with patch.object(
            transaction_service.transaction_repository,
            "find_transactions",
        ) as mock_find:
            mock_find.return_value = []
            resolution: Sequence[TransactionPublicWithRelations] = (
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
        self,
        transaction_service: TransactionService,
        account_repository: AccountRepository,
        sample_transactions,
        sample_accounts,
    ):
        """Test that deleting a transaction doesn't delete the related account."""
        transaction_id = sample_transactions[0].id
        account_id = sample_transactions[0].account_id

        result = transaction_service.delete_transaction(transaction_id)
        assert result is True

        # Verify account still exists
        account = account_repository.get_account_by_id(account_id)
        assert account is not None

    def test_delete_transaction_does_not_cascade_to_security(
        self,
        transaction_service: TransactionService,
        security_repository: SecurityRepository,
        sample_transactions,
        sample_securities,
    ):
        """Test that deleting a transaction doesn't delete the related security."""
        transaction_id = sample_transactions[0].id
        security_key = sample_transactions[0].security_key

        result = transaction_service.delete_transaction(transaction_id)
        assert result is True

        # Verify security still exists
        security = security_repository.get_security_by_key(security_key)
        assert security is not None

"""Tests for ParsingService."""

import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from niveshpy.models.account import AccountCreate
from niveshpy.models.parser import Parser
from niveshpy.models.security import SecurityCategory, SecurityCreate, SecurityType
from niveshpy.models.transaction import TransactionCreate, TransactionType
from niveshpy.services.parsing import ParsingService
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
def transaction_repository(
    account_repository: MockAccountRepository,
    security_repository: MockSecurityRepository,
) -> MockTransactionRepository:
    """Create MockTransactionRepository instance with the mocked repositories."""
    return MockTransactionRepository(account_repository, security_repository)


@pytest.fixture
def mock_parser():
    """Create a mock parser with test data."""
    parser = MagicMock(spec=Parser)

    # Setup default return values
    parser.get_date_range.return_value = (
        datetime.date(2024, 1, 1),
        datetime.date(2024, 12, 31),
    )

    parser.get_accounts.return_value = [
        AccountCreate(name="Test Account 1", institution="Test Bank", properties={}),
        AccountCreate(name="Test Account 2", institution="Test Bank", properties={}),
    ]

    parser.get_securities.return_value = [
        SecurityCreate(
            key="SEC001",
            name="Test Security 1",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            properties={},
        ),
        SecurityCreate(
            key="SEC002",
            name="Test Security 2",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
        ),
    ]

    # get_transactions needs accounts parameter
    def get_transactions_mock(accounts):
        return [
            TransactionCreate(
                transaction_date=datetime.date(2024, 6, 1),
                type=TransactionType.PURCHASE,
                description="Test Transaction 1",
                amount=Decimal("1000.00"),
                units=Decimal("10.00"),
                security_key="SEC001",
                account_id=accounts[0].id,
                properties={},
            ),
            TransactionCreate(
                transaction_date=datetime.date(2024, 6, 15),
                type=TransactionType.SALE,
                description="Test Transaction 2",
                amount=Decimal("2000.00"),
                units=Decimal("5.00"),
                security_key="SEC002",
                account_id=accounts[1].id,
                properties={},
            ),
        ]

    parser.get_transactions.side_effect = get_transactions_mock

    return parser


@pytest.fixture
def parsing_service(
    mock_parser: Parser,
    account_repository: MockAccountRepository,
    security_repository: MockSecurityRepository,
    transaction_repository: MockTransactionRepository,
):
    """Create ParsingService instance with mock parser and mocked repositories."""
    return ParsingService(
        parser=mock_parser,
        account_repository=account_repository,
        security_repository=security_repository,
        transaction_repository=transaction_repository,
    )


@pytest.fixture
def progress_callback():
    """Create a progress callback mock."""
    return MagicMock()


@pytest.fixture
def parsing_service_with_callback(
    mock_parser: Parser,
    account_repository: MockAccountRepository,
    security_repository: MockSecurityRepository,
    transaction_repository: MockTransactionRepository,
    progress_callback,
):
    """Create ParsingService instance with progress callback and mocked repositories."""
    return ParsingService(
        parser=mock_parser,
        account_repository=account_repository,
        security_repository=security_repository,
        transaction_repository=transaction_repository,
        progress_callback=progress_callback,
    )


class TestParsingService:
    """Tests for ParsingService public API."""

    def test_parse_stores_all_entities(
        self,
        parsing_service: ParsingService,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
        transaction_repository: MockTransactionRepository,
    ):
        """Test that parse_and_store_all stores accounts, securities, and transactions."""
        parsing_service.parse_and_store_all()

        # Verify data was stored correctly
        accounts = account_repository.find_accounts([])
        securities = security_repository.find_securities([])
        transactions = transaction_repository.find_transactions([])

        assert len(accounts) == 2
        assert len(securities) == 2
        assert len(transactions) == 2

        # Verify account data
        assert accounts[0].name == "Test Account 1"
        assert accounts[0].institution == "Test Bank"
        assert accounts[1].name == "Test Account 2"

        # Verify security data
        assert securities[0].key == "SEC001"
        assert securities[0].name == "Test Security 1"
        assert securities[1].key == "SEC002"

        # Verify transaction data
        transactions = sorted(
            transactions, key=lambda t: t.description
        )  # Sort for consistent order
        assert transactions[0].description == "Test Transaction 1"
        assert transactions[0].type == TransactionType.PURCHASE
        assert transactions[1].description == "Test Transaction 2"
        assert transactions[1].type == TransactionType.SALE

    def test_parse_adds_metadata_to_all_entities(
        self,
        parsing_service,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
        transaction_repository: MockTransactionRepository,
    ):
        """Test that all parsed entities get source='parser' metadata."""
        parsing_service.parse_and_store_all()

        accounts = account_repository.find_accounts([])
        securities = security_repository.find_securities([])
        transactions = transaction_repository.find_transactions([])

        # All entities should have source metadata
        assert all(acc.properties.get("source") == "parser" for acc in accounts)
        assert all(sec.properties.get("source") == "parser" for sec in securities)
        assert all(txn.properties.get("source") == "parser" for txn in transactions)

    def test_parse_with_progress_callback(
        self, parsing_service_with_callback, progress_callback
    ):
        """Test that progress callback is invoked for all parsing stages."""
        parsing_service_with_callback.parse_and_store_all()

        # Verify callback was invoked for each stage
        callback_stages = [call[0][0] for call in progress_callback.call_args_list]
        assert "accounts" in callback_stages
        assert "securities" in callback_stages
        assert "transactions" in callback_stages

    def test_parse_empty_data(
        self,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
        transaction_repository: MockTransactionRepository,
    ):
        """Test parsing when parser returns no data."""
        empty_parser = MagicMock()
        empty_parser.get_date_range.return_value = (
            datetime.date(2024, 1, 1),
            datetime.date(2024, 12, 31),
        )
        empty_parser.get_accounts.return_value = []
        empty_parser.get_securities.return_value = []
        empty_parser.get_transactions.return_value = []

        service = ParsingService(
            parser=empty_parser,
            account_repository=account_repository,
            security_repository=security_repository,
            transaction_repository=transaction_repository,
        )
        service.parse_and_store_all()

        # Should not crash, database should remain empty
        assert len(account_repository.find_accounts([])) == 0
        assert len(security_repository.find_securities([])) == 0
        assert len(transaction_repository.find_transactions([])) == 0

    def test_parse_twice_no_updates_accounts(
        self,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
        transaction_repository: MockTransactionRepository,
        mock_parser,
    ):
        """Test that parsing same accounts twice does not modify them."""
        # First parse
        service = ParsingService(
            parser=mock_parser,
            account_repository=account_repository,
            security_repository=security_repository,
            transaction_repository=transaction_repository,
        )
        service.parse_and_store_all()

        # Modify parser to return updated account data
        mock_parser.get_accounts.return_value = [
            AccountCreate(
                name="Test Account 1",
                institution="Test Bank",
                properties={"updated": True},
            ),
            AccountCreate(
                name="Test Account 2",
                institution="Test Bank",
                properties={"updated": True},
            ),
        ]

        # Second parse
        service.parse_and_store_all()

        # Should still have only 2 accounts (updated, not duplicated)
        accounts = account_repository.find_accounts([])
        assert len(accounts) == 2
        assert all("updated" not in acc.properties for acc in accounts)

    def test_parse_twice_no_updates_securities(
        self,
        mock_parser,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
        transaction_repository: MockTransactionRepository,
    ):
        """Test that parsing same securities twice does not modify them."""
        # First parse
        service = ParsingService(
            parser=mock_parser,
            account_repository=account_repository,
            security_repository=security_repository,
            transaction_repository=transaction_repository,
        )
        service.parse_and_store_all()

        # Modify parser to return updated security data
        mock_parser.get_securities.return_value = [
            SecurityCreate(
                key="SEC001",
                name="Updated Security 1",
                type=SecurityType.MUTUAL_FUND,
                category=SecurityCategory.EQUITY,
                properties={},
            ),
            SecurityCreate(
                key="SEC002",
                name="Updated Security 2",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
                properties={},
            ),
        ]

        # Second parse
        service.parse_and_store_all()

        # Should still have only 2 securities with updated names
        securities = security_repository.find_securities([])
        assert len(securities) == 2
        assert securities[0].name == "Test Security 1"
        assert securities[1].name == "Test Security 2"

    def test_parse_twice_replaces_transactions_in_date_range(
        self,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
        transaction_repository: MockTransactionRepository,
    ):
        """Test that re-parsing replaces transactions in the same date range."""
        parser = MagicMock()
        parser.get_date_range.return_value = (
            datetime.date(2024, 1, 1),
            datetime.date(2024, 12, 31),
        )
        parser.get_accounts.return_value = [
            AccountCreate(name="Test Account", institution="Test Bank", properties={}),
        ]
        parser.get_securities.return_value = [
            SecurityCreate(
                key="SEC001",
                name="Test Security",
                type=SecurityType.MUTUAL_FUND,
                category=SecurityCategory.EQUITY,
                properties={},
            ),
        ]

        # First parse with initial transactions
        def first_transactions(accounts):
            return [
                TransactionCreate(
                    transaction_date=datetime.date(2024, 6, 1),
                    type=TransactionType.PURCHASE,
                    description="Original Transaction",
                    amount=Decimal("1000.00"),
                    units=Decimal("10.00"),
                    security_key="SEC001",
                    account_id=accounts[0].id,
                    properties={},
                ),
            ]

        parser.get_transactions.side_effect = first_transactions
        service = ParsingService(
            parser=parser,
            account_repository=account_repository,
            security_repository=security_repository,
            transaction_repository=transaction_repository,
        )
        service.parse_and_store_all()

        # Verify first transaction was stored
        transactions = transaction_repository.find_transactions([])
        assert len(transactions) == 1
        assert transactions[0].description == "Original Transaction"

        # Second parse with different transactions
        def second_transactions(accounts):
            return [
                TransactionCreate(
                    transaction_date=datetime.date(2024, 6, 15),
                    type=TransactionType.SALE,
                    description="New Transaction",
                    amount=Decimal("2000.00"),
                    units=Decimal("5.00"),
                    security_key="SEC001",
                    account_id=accounts[0].id,
                    properties={},
                ),
            ]

        parser.get_transactions.side_effect = second_transactions
        service.parse_and_store_all()

        # Original transaction should be replaced
        transactions = transaction_repository.find_transactions([])
        assert len(transactions) == 1
        assert transactions[0].description == "New Transaction"

    def test_parse_preserves_transactions_from_other_accounts(
        self,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
        transaction_repository: MockTransactionRepository,
    ):
        """Test that parsing one account doesn't delete transactions from other accounts."""
        # Create two parsers for two different accounts
        parser1 = MagicMock()
        parser1.get_date_range.return_value = (
            datetime.date(2024, 1, 1),
            datetime.date(2024, 12, 31),
        )
        parser1.get_accounts.return_value = [
            AccountCreate(name="Account 1", institution="Bank 1", properties={}),
        ]
        parser1.get_securities.return_value = [
            SecurityCreate(
                key="SEC001",
                name="Security 1",
                type=SecurityType.MUTUAL_FUND,
                category=SecurityCategory.EQUITY,
                properties={},
            ),
        ]

        def transactions_account1(accounts):
            return [
                TransactionCreate(
                    transaction_date=datetime.date(2024, 6, 1),
                    type=TransactionType.PURCHASE,
                    description="Account 1 Transaction",
                    amount=Decimal("1000.00"),
                    units=Decimal("10.00"),
                    security_key="SEC001",
                    account_id=accounts[0].id,
                    properties={},
                ),
            ]

        parser1.get_transactions.side_effect = transactions_account1

        parser2 = MagicMock()
        parser2.get_date_range.return_value = (
            datetime.date(2024, 1, 1),
            datetime.date(2024, 12, 31),
        )
        parser2.get_accounts.return_value = [
            AccountCreate(name="Account 2", institution="Bank 2", properties={}),
        ]
        parser2.get_securities.return_value = [
            SecurityCreate(
                key="SEC002",
                name="Security 2",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
                properties={},
            ),
        ]

        def transactions_account2(accounts):
            return [
                TransactionCreate(
                    transaction_date=datetime.date(2024, 6, 15),
                    type=TransactionType.SALE,
                    description="Account 2 Transaction",
                    amount=Decimal("2000.00"),
                    units=Decimal("5.00"),
                    security_key="SEC002",
                    account_id=accounts[0].id,
                    properties={},
                ),
            ]

        parser2.get_transactions.side_effect = transactions_account2

        # Parse first account
        service1 = ParsingService(
            parser=parser1,
            account_repository=account_repository,
            security_repository=security_repository,
            transaction_repository=transaction_repository,
        )
        service1.parse_and_store_all()

        # Parse second account
        service2 = ParsingService(
            parser=parser2,
            account_repository=account_repository,
            security_repository=security_repository,
            transaction_repository=transaction_repository,
        )
        service2.parse_and_store_all()

        # Both transactions should exist
        transactions = transaction_repository.find_transactions([])
        assert len(transactions) == 2

        descriptions = {txn.description for txn in transactions}
        assert "Account 1 Transaction" in descriptions
        assert "Account 2 Transaction" in descriptions

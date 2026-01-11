"""Tests for report service."""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlmodel import Session

from niveshpy.exceptions import InvalidInputError
from niveshpy.models.account import Account
from niveshpy.models.price import Price
from niveshpy.models.report import Holding
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.models.transaction import Transaction, TransactionType
from niveshpy.services.report import get_holdings


@pytest.fixture
def sample_accounts(session: Session) -> list[Account]:
    """Create sample accounts for testing."""
    accounts = [
        Account(name="Savings Account", institution="HDFC Bank"),
        Account(name="Investment Account", institution="ICICI"),
        Account(name="Pension Account", institution="SBI"),
    ]
    session.add_all(accounts)
    session.commit()
    for account in accounts:
        session.refresh(account)
    return accounts


@pytest.fixture
def sample_securities(session: Session) -> list[Security]:
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
        Security(
            key="TCS",
            name="TCS Limited",
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
    sample_accounts: list[Account],
    sample_securities: list[Security],
) -> list[Transaction]:
    """Create sample transactions for testing."""
    transactions = [
        # Account 0 - HDFC Equity Fund: Buy 100, Sell 20 = 80 units
        Transaction(
            transaction_date=datetime.date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Purchase HDFC Fund",
            amount=Decimal("10000.00"),
            units=Decimal("100.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
        Transaction(
            transaction_date=datetime.date(2024, 2, 20),
            type=TransactionType.SALE,
            description="Sold HDFC Fund",
            amount=Decimal("2000.00"),
            units=Decimal("-20.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
        # Account 1 - ICICI Liquid Fund: Buy 50 units
        Transaction(
            transaction_date=datetime.date(2024, 3, 10),
            type=TransactionType.PURCHASE,
            description="Purchase ICICI Fund",
            amount=Decimal("5000.00"),
            units=Decimal("50.000"),
            account_id=sample_accounts[1].id,
            security_key=sample_securities[1].key,
        ),
        # Account 0 - Reliance Stock: Buy 25 units
        Transaction(
            transaction_date=datetime.date(2024, 4, 5),
            type=TransactionType.PURCHASE,
            description="Purchase Reliance",
            amount=Decimal("25000.00"),
            units=Decimal("25.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[2].key,
        ),
        # Account 2 - TCS Stock: Buy 10, Sell 10 = 0 units (should be excluded)
        Transaction(
            transaction_date=datetime.date(2024, 5, 1),
            type=TransactionType.PURCHASE,
            description="Purchase TCS",
            amount=Decimal("30000.00"),
            units=Decimal("10.000"),
            account_id=sample_accounts[2].id,
            security_key=sample_securities[3].key,
        ),
        Transaction(
            transaction_date=datetime.date(2024, 5, 15),
            type=TransactionType.SALE,
            description="Sold all TCS",
            amount=Decimal("32000.00"),
            units=Decimal("-10.000"),
            account_id=sample_accounts[2].id,
            security_key=sample_securities[3].key,
        ),
    ]
    session.add_all(transactions)
    session.commit()
    for txn in transactions:
        session.refresh(txn)
    return transactions


@pytest.fixture
def sample_prices(
    session: Session,
    sample_securities: list[Security],
) -> list[Price]:
    """Create sample prices for testing."""
    prices = [
        # HDFC Equity Fund prices
        Price(
            security_key=sample_securities[0].key,
            date=datetime.date(2024, 6, 1),
            open=Decimal("105.00"),
            high=Decimal("110.00"),
            low=Decimal("103.00"),
            close=Decimal("108.00"),
        ),
        Price(
            security_key=sample_securities[0].key,
            date=datetime.date(2024, 6, 15),
            open=Decimal("108.00"),
            high=Decimal("112.00"),
            low=Decimal("107.00"),
            close=Decimal("110.00"),
        ),
        # ICICI Liquid Fund prices
        Price(
            security_key=sample_securities[1].key,
            date=datetime.date(2024, 6, 1),
            open=Decimal("101.00"),
            high=Decimal("101.50"),
            low=Decimal("100.50"),
            close=Decimal("101.00"),
        ),
        # Reliance Stock prices
        Price(
            security_key=sample_securities[2].key,
            date=datetime.date(2024, 6, 10),
            open=Decimal("1000.00"),
            high=Decimal("1050.00"),
            low=Decimal("995.00"),
            close=Decimal("1020.00"),
        ),
        # TCS Stock prices (for zero-balance security)
        Price(
            security_key=sample_securities[3].key,
            date=datetime.date(2024, 6, 1),
            open=Decimal("3000.00"),
            high=Decimal("3100.00"),
            low=Decimal("2950.00"),
            close=Decimal("3050.00"),
        ),
    ]
    session.add_all(prices)
    session.commit()
    for price in prices:
        session.refresh(price)
    return prices


class TestGetHoldings:
    """Tests for get_holdings function."""

    def test_get_all_holdings(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting all holdings without filters."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=0)

        # Should return 3 holdings (excluding TCS with 0 balance)
        assert len(holdings) == 3
        assert all(isinstance(h, Holding) for h in holdings)

    def test_get_holdings_correct_values(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings have correct calculated values."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=0)

        # Find HDFC Equity Fund holding (80 units * 110 = 8800)
        hdfc_holding = next(h for h in holdings if h.security.key == "123456")
        assert hdfc_holding.units == Decimal("80.000")
        assert hdfc_holding.amount == Decimal("8800.00")
        assert hdfc_holding.date == datetime.date(2024, 6, 15)  # Latest date
        assert hdfc_holding.account.name == "Savings Account"

        # Find ICICI Liquid Fund holding (50 units * 101 = 5050)
        icici_holding = next(h for h in holdings if h.security.key == "234567")
        assert icici_holding.units == Decimal("50.000")
        assert icici_holding.amount == Decimal("5050.00")
        assert icici_holding.account.name == "Investment Account"

        # Find Reliance Stock holding (25 units * 1020 = 25500)
        reli_holding = next(h for h in holdings if h.security.key == "RELI")
        assert reli_holding.units == Decimal("25.000")
        assert reli_holding.amount == Decimal("25500.00")
        assert reli_holding.account.name == "Savings Account"

    def test_get_holdings_excludes_zero_balance(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings with zero or near-zero balance are excluded."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=0)

        # TCS with 0 balance should be excluded
        tcs_holdings = [h for h in holdings if h.security.key == "TCS"]
        assert len(tcs_holdings) == 0

    def test_get_holdings_with_limit(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with limit."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=2, offset=0)

        assert len(holdings) == 2

    def test_get_holdings_with_offset(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with offset."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=1)

        assert len(holdings) == 2

    def test_get_holdings_with_limit_and_offset(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with both limit and offset."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=1, offset=1)

        assert len(holdings) == 1

    def test_get_holdings_offset_beyond_total(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with offset beyond total count."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=10)

        assert len(holdings) == 0

    def test_get_holdings_with_security_filter(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with security filter."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=("HDFC",), limit=30, offset=0)

        # Should return only HDFC Equity Fund
        assert len(holdings) == 1
        assert holdings[0].security.key == "123456"

    def test_get_holdings_with_account_filter(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with account filter."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=("acct:Savings",), limit=30, offset=0)

        # Should return holdings from Savings Account (HDFC Fund and Reliance Stock)
        assert len(holdings) == 2
        assert all(h.account.name == "Savings Account" for h in holdings)

    def test_get_holdings_with_security_text_filter(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings filtered by security text (searches type/category/name/key)."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=("STOCK",), limit=30, offset=0)

        # Should return only stock holdings (searches all security fields)
        assert len(holdings) == 1
        assert holdings[0].security.type == SecurityType.STOCK

    def test_get_holdings_with_institution_filter(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings filtered by account institution."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=("acct:ICICI",), limit=30, offset=0)

        # Should return holdings from ICICI account
        assert len(holdings) == 1
        assert holdings[0].account.institution == "ICICI"

    def test_get_holdings_with_multiple_filters(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with multiple query filters."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(
                queries=("acct:Savings", "HDFC"), limit=30, offset=0
            )

        # Should return only HDFC Equity Fund (Savings + HDFC in name)
        assert len(holdings) == 1
        assert holdings[0].security.key == "123456"
        assert holdings[0].account.name == "Savings Account"

    def test_get_holdings_query_no_matches(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with query that has no matches."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=("NonExistent",), limit=30, offset=0)

        assert len(holdings) == 0

    def test_get_holdings_empty_database(self, session):
        """Test getting holdings when database is empty."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=0)

        assert len(holdings) == 0

    def test_get_holdings_invalid_limit(self, session):
        """Test that invalid limit raises InvalidInputError."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            with pytest.raises(InvalidInputError, match="Limit must be positive"):
                get_holdings(queries=(), limit=0, offset=0)

    def test_get_holdings_negative_limit(self, session):
        """Test that negative limit raises InvalidInputError."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            with pytest.raises(InvalidInputError, match="Limit must be positive"):
                get_holdings(queries=(), limit=-1, offset=0)

    def test_get_holdings_invalid_offset(self, session):
        """Test that negative offset raises InvalidInputError."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            with pytest.raises(InvalidInputError, match="Offset cannot be negative"):
                get_holdings(queries=(), limit=30, offset=-1)

    def test_get_holdings_uses_latest_price(
        self, session, sample_accounts, sample_securities, sample_transactions
    ):
        """Test that holdings use the latest price for each security."""
        # Add multiple prices with different dates
        prices = [
            Price(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 1),
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("99.00"),
                close=Decimal("102.00"),
            ),
            Price(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 15),
                open=Decimal("102.00"),
                high=Decimal("108.00"),
                low=Decimal("101.00"),
                close=Decimal("105.00"),  # Latest price
            ),
            Price(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 10),
                open=Decimal("101.00"),
                high=Decimal("106.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
            ),
        ]
        session.add_all(prices)
        session.commit()

        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=("123456",), limit=30, offset=0)

        # Should use the latest price (105.00 from June 15)
        assert len(holdings) == 1
        assert holdings[0].amount == Decimal("8400.00")  # 80 units * 105.00
        assert holdings[0].date == datetime.date(2024, 6, 15)

    def test_get_holdings_ordering(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings are ordered by account_id and security_key."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=0)

        # Verify ordering: should be sorted by account_id, then security_key
        assert len(holdings) == 3
        # First two should be from account 0 (Savings)
        assert holdings[0].account.name == "Savings Account"
        assert holdings[1].account.name == "Savings Account"
        # Third should be from account 1 (Investment)
        assert holdings[2].account.name == "Investment Account"

    def test_get_holdings_decimal_precision(
        self, session, sample_accounts, sample_securities, sample_transactions
    ):
        """Test that holdings maintain correct decimal precision."""
        # Add price with many decimal places
        price = Price(
            security_key=sample_securities[0].key,
            date=datetime.date(2024, 6, 1),
            open=Decimal("105.123456"),
            high=Decimal("110.123456"),
            low=Decimal("103.123456"),
            close=Decimal("108.123456"),
        )
        session.add(price)
        session.commit()

        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=("123456",), limit=30, offset=0)

        # Units should have 3 decimal places, amount should have 2
        assert len(holdings) == 1
        assert holdings[0].units == Decimal("80.000")
        # 80 * 108.123456 = 8649.87648, rounded to 8649.88
        assert holdings[0].amount == Decimal("8649.88")

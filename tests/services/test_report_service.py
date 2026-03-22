"""Tests for report service."""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlmodel import Session

from niveshpy.exceptions import InvalidInputError, OperationError
from niveshpy.models.account import Account
from niveshpy.models.price import Price
from niveshpy.models.report import (
    Allocation,
    AllocationByCategory,
    AllocationByType,
    Holding,
    PerformanceHolding,
    SummaryResult,
)
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.models.transaction import Transaction, TransactionType
from niveshpy.services.report import (
    compute_portfolio_totals,
    get_allocation,
    get_holdings,
    get_performance,
    get_summary,
)


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
            amount=Decimal("-2000.00"),
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
            amount=Decimal("-32000.00"),
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

    def test_get_holdings_invested_amounts(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings include correct invested amounts using FIFO."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=0)

        # HDFC: Buy 100 @ 10000, Sell 20 → remaining 80 units, invested = 10000 * 80/100 = 8000
        hdfc = next(h for h in holdings if h.security.key == "123456")
        assert hdfc.invested == Decimal("8000.00")

        # ICICI: Buy 50 @ 5000, no sales → invested = 5000
        icici = next(h for h in holdings if h.security.key == "234567")
        assert icici.invested == Decimal("5000.00")

        # Reliance: Buy 25 @ 25000, no sales → invested = 25000
        reli = next(h for h in holdings if h.security.key == "RELI")
        assert reli.invested == Decimal("25000.00")

    def test_get_holdings_gains(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings have correct gains (amount - invested)."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=0)

        # HDFC: amount=8800, invested=8000
        hdfc = next(h for h in holdings if h.security.key == "123456")
        assert hdfc.amount - hdfc.invested == Decimal("800.00")

        # ICICI: amount=5050, invested=5000
        icici = next(h for h in holdings if h.security.key == "234567")
        assert icici.amount - icici.invested == Decimal("50.00")

        # Reliance: amount=25500, invested=25000
        reli = next(h for h in holdings if h.security.key == "RELI")
        assert reli.amount - reli.invested == Decimal("500.00")

    def test_get_holdings_invested_consistency(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that invested is present for all holdings with purchase history."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            holdings = get_holdings(queries=(), limit=30, offset=0)

        for h in holdings:
            assert h.invested is not None

    def test_get_holdings_raises_when_no_purchase_history(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_prices,
    ):
        """Test that get_holdings raises OperationError when purchase history is incomplete."""
        # Create a sale without a prior purchase
        txn = Transaction(
            transaction_date=datetime.date(2024, 1, 15),
            type=TransactionType.SALE,
            description="Mystery sale",
            amount=Decimal("-5000.00"),
            units=Decimal("-50.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        )
        session.add(txn)
        session.commit()
        # Also add a purchase so there's a holding
        txn2 = Transaction(
            transaction_date=datetime.date(2024, 2, 1),
            type=TransactionType.PURCHASE,
            description="Buy fund",
            amount=Decimal("10000.00"),
            units=Decimal("100.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        )
        session.add(txn2)
        session.commit()

        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            with pytest.raises(OperationError, match="Insufficient purchase history"):
                get_holdings(queries=(), limit=30, offset=0)


class TestGetAllocation:
    """Tests for get_allocation function."""

    def test_get_allocation_by_both(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation grouped by both type and category."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="both")

        # Should return allocations grouped by type and category
        assert len(allocations) > 0
        assert all(isinstance(a, Allocation) for a in allocations)
        # All allocations should sum to approximately 1.0 (100%)
        total_allocation = sum(a.allocation for a in allocations)
        assert abs(total_allocation - Decimal("1.0")) <= Decimal("0.0001")

    def test_get_allocation_by_type(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation grouped by type only."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="type")

        # Should return allocations grouped by type
        assert len(allocations) > 0
        assert all(isinstance(a, AllocationByType) for a in allocations)
        # Total should be 100%
        total_allocation = sum(a.allocation for a in allocations)
        assert abs(total_allocation - Decimal("1.0")) < Decimal("0.0001")

    def test_get_allocation_by_category(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation grouped by category only."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="category")

        # Should return allocations grouped by category
        assert len(allocations) > 0
        assert all(isinstance(a, AllocationByCategory) for a in allocations)
        # Total should be 100%
        total_allocation = sum(a.allocation for a in allocations)
        assert abs(total_allocation - Decimal("1.0")) < Decimal("0.0001")

    def test_get_allocation_correct_values_by_both(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocations have correct calculated values when grouped by both."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="both")

        # Calculate total value from expected holdings
        # HDFC Fund (MUTUAL_FUND, EQUITY): 80 * 110 = 8800
        # ICICI Fund (MUTUAL_FUND, DEBT): 50 * 101 = 5050
        # Reliance (STOCK, EQUITY): 25 * 1020 = 25500
        total_value = Decimal("39350.00")

        # Verify allocations
        for alloc in allocations:
            assert isinstance(alloc, Allocation)
            if (
                alloc.security_type == SecurityType.MUTUAL_FUND
                and alloc.security_category == SecurityCategory.EQUITY
            ):
                assert alloc.amount == Decimal("8800.00")
                assert abs(
                    alloc.allocation - (Decimal("8800.00") / total_value)
                ) < Decimal("0.0001")
            elif (
                alloc.security_type == SecurityType.MUTUAL_FUND
                and alloc.security_category == SecurityCategory.DEBT
            ):
                assert alloc.amount == Decimal("5050.00")
                assert abs(
                    alloc.allocation - (Decimal("5050.00") / total_value)
                ) < Decimal("0.0001")
            elif (
                alloc.security_type == SecurityType.STOCK
                and alloc.security_category == SecurityCategory.EQUITY
            ):
                assert alloc.amount == Decimal("25500.00")
                assert abs(
                    alloc.allocation - (Decimal("25500.00") / total_value)
                ) < Decimal("0.0001")

    def test_get_allocation_by_type_aggregates_correctly(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocation by type aggregates multiple categories correctly."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="type")

        # MUTUAL_FUND: 8800 (EQUITY) + 5050 (DEBT) = 13850
        # STOCK: 25500
        # Total: 39350
        total_value = Decimal("39350.00")

        for alloc in allocations:
            assert isinstance(alloc, AllocationByType)

            if alloc.security_type == SecurityType.MUTUAL_FUND:
                assert alloc.amount == Decimal("13850.00")
                assert abs(
                    alloc.allocation - (Decimal("13850.00") / total_value)
                ) < Decimal("0.0001")
            elif alloc.security_type == SecurityType.STOCK:
                # Second allocation should be STOCK
                assert alloc.security_type == SecurityType.STOCK
                assert alloc.amount == Decimal("25500.00")
                assert abs(
                    alloc.allocation - (Decimal("25500.00") / total_value)
                ) < Decimal("0.0001")
            else:  # pragma: no cover
                # Should not reach here
                pytest.fail(
                    f"Unexpected security type in allocation: {alloc.security_type}"
                )

    def test_get_allocation_by_category_aggregates_correctly(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocation by category aggregates multiple types correctly."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="category")

        # EQUITY: 8800 (MF) + 25500 (STOCK) = 34300
        # DEBT: 5050 (MF)
        # Total: 39350
        total_value = Decimal("39350.00")

        for alloc in allocations:
            assert isinstance(alloc, AllocationByCategory)

            if alloc.security_category == SecurityCategory.EQUITY:
                assert alloc.amount == Decimal("34300.00")
                assert abs(
                    alloc.allocation - (Decimal("34300.00") / total_value)
                ) < Decimal("0.0001")
            elif alloc.security_category == SecurityCategory.DEBT:
                assert alloc.amount == Decimal("5050.00")
                assert abs(
                    alloc.allocation - (Decimal("5050.00") / total_value)
                ) < Decimal("0.0001")
            else:  # pragma: no cover
                # Should not reach here
                pytest.fail(
                    f"Unexpected security category in allocation: {alloc.security_category}"
                )

    def test_get_allocation_with_security_filter(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation with security filter."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=("HDFC",), group_by="both")

        # Should return only HDFC Fund allocation
        assert len(allocations) == 1
        assert isinstance(allocations[0], Allocation)
        assert allocations[0].allocation == Decimal("1.0000")
        assert allocations[0].security_type == SecurityType.MUTUAL_FUND
        assert allocations[0].security_category == SecurityCategory.EQUITY

    def test_get_allocation_with_account_filter(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation with account filter."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=("acct:Savings",), group_by="both")

        # Should return allocations from Savings Account (HDFC Fund and Reliance)
        assert len(allocations) == 2
        total_alloc = sum(a.allocation for a in allocations)
        assert abs(total_alloc - Decimal("1.0")) < Decimal("0.0001")

    def test_get_allocation_empty_database(self, session):
        """Test getting allocation when database is empty."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="both")

        assert len(allocations) == 0

    def test_get_allocation_excludes_zero_balance(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocation excludes holdings with zero balance."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="both")

        # TCS (zero balance) should not appear in allocations
        for alloc in allocations:
            assert isinstance(alloc, Allocation)
            # TCS is the only STOCK, so if we had TCS, STOCK would have different values
            if alloc.security_type == SecurityType.STOCK:
                # Only Reliance should be included
                assert alloc.amount == Decimal("25500.00")

    def test_get_allocation_ordered_by_amount_desc(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocations are ordered by amount descending."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=(), group_by="both")

        # Verify ordering
        amounts = [a.amount for a in allocations]
        assert amounts == sorted(amounts, reverse=True)

    def test_get_allocation_uses_latest_price(
        self, session, sample_accounts, sample_securities, sample_transactions
    ):
        """Test that allocation uses the latest price for each security."""
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
        ]
        session.add_all(prices)
        session.commit()

        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(queries=("123456",), group_by="both")

        # Should use the latest price (105.00 from June 15)
        assert len(allocations) == 1
        assert allocations[0].amount == Decimal("8400.00")  # 80 units * 105.00

    def test_get_allocation_decimal_precision(
        self, session, sample_accounts, sample_securities, sample_transactions
    ):
        """Test that allocation maintains correct decimal precision."""
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

            allocations = get_allocation(queries=("123456",), group_by="both")

        # Amount should have 2 decimal places, allocation should have 4
        assert len(allocations) == 1
        # 80 * 108.123456 = 8649.87648, rounded to 8649.88
        assert allocations[0].amount == Decimal("8649.88")
        assert allocations[0].allocation == Decimal("1.0000")

    def test_get_allocation_with_multiple_filters(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation with multiple query filters."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            allocations = get_allocation(
                queries=("acct:Savings", "HDFC"), group_by="both"
            )

        # Should return only HDFC Equity Fund (Savings + HDFC in name)
        assert len(allocations) == 1
        assert allocations[0].allocation == Decimal("1.0000")


def _make_holding(
    *,
    amount: str,
    invested: str | None = None,
    gains: str | None = None,
    key: str = "TEST",
    name: str = "Test Fund",
) -> Holding:
    """Create a Holding object for testing compute_portfolio_totals."""
    account = Account(id=1, name="Test", institution="Test")
    security = Security(
        key=key,
        name=name,
        type=SecurityType.MUTUAL_FUND,
        category=SecurityCategory.EQUITY,
    )
    inv = Decimal(invested) if invested is not None else None
    amt = Decimal(amount)
    return Holding(
        account=account,
        security=security,
        date=datetime.date.today(),
        units=Decimal("100"),
        amount=amt,
        invested=inv,
    )


class TestComputePortfolioTotals:
    """Tests for compute_portfolio_totals function."""

    def test_basic_totals(self):
        """Two holdings with invested amounts produce correct aggregate sums."""
        holdings = [
            _make_holding(amount="15000", invested="10000", gains="5000", key="SEC1"),
            _make_holding(amount="8000", invested="6000", gains="2000", key="SEC2"),
        ]
        result = compute_portfolio_totals(holdings)
        assert result.total_current_value == Decimal("23000.00")
        assert result.total_invested == Decimal("16000.00")
        assert result.total_gains == Decimal("7000.00")
        assert result.last_updated == datetime.date.today()

    def test_none_invested(self):
        """Holdings where invested is None yield None for total_invested and gains."""
        holdings = [
            _make_holding(amount="15000", key="SEC1"),
            _make_holding(amount="8000", key="SEC2"),
        ]
        result = compute_portfolio_totals(holdings)
        assert result.total_current_value == Decimal("23000.00")
        assert result.total_invested is None
        assert result.total_gains is None
        assert result.gains_percentage is None

    def test_mixed_invested(self):
        """Mix of holdings with and without invested computes gains from known only."""
        holdings = [
            _make_holding(amount="15000", invested="10000", gains="5000", key="SEC1"),
            _make_holding(amount="8000", key="SEC2"),
        ]
        result = compute_portfolio_totals(holdings)
        assert result.total_current_value == Decimal("23000.00")
        assert result.total_invested == Decimal("10000.00")
        # gains computed only from SEC1 (known invested): 15000 - 10000 = 5000
        assert result.total_gains == Decimal("5000.00")

    def test_empty_holdings_raises(self):
        """Empty holdings list should raise OperationError."""
        with pytest.raises(OperationError, match="No holdings available"):
            compute_portfolio_totals([])

    def test_zero_invested(self):
        """Holdings with 0 invested yield None gains_percentage to avoid div by zero."""
        holdings = [
            _make_holding(amount="5000", invested="0", gains="5000"),
        ]
        result = compute_portfolio_totals(holdings)
        assert result.total_invested == Decimal("0.00")
        assert result.gains_percentage is None

    def test_gains_percentage(self):
        """Verify correct fraction calculation: gains / invested."""
        holdings = [
            _make_holding(amount="12000", invested="10000", gains="2000", key="SEC1"),
            _make_holding(amount="5500", invested="5000", gains="500", key="SEC2"),
        ]
        result = compute_portfolio_totals(holdings)
        # total_current = 17500, total_invested = 15000
        # gains = 2500, fraction = 2500 / 15000 = 0.1667
        assert result.gains_percentage == Decimal("0.1667")


class TestGetPerformance:
    """Tests for get_performance function."""

    def test_returns_holdings_with_xirr(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Returns PerformanceResult with holdings, totals, and portfolio XIRR."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_performance(queries=())

        # Should have 3 holdings (HDFC 80u, ICICI 50u, RELI 25u; TCS sold out)
        assert len(result.holdings) == 3
        assert result.totals.total_current_value > Decimal("0")
        assert result.totals.total_invested is not None
        assert result.totals.total_invested > Decimal("0")
        assert result.totals.total_gains is not None
        assert result.totals.gains_percentage is not None
        assert result.totals.xirr is not None

        # Each result is a PerformanceHolding
        for h in result.holdings:
            assert isinstance(h, PerformanceHolding)
            assert h.current_value > Decimal("0")
            # XIRR may be None for some holdings, but most should compute

    def test_per_holding_xirr_values(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Each holding gets its own XIRR computed from its own transactions."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_performance(queries=())

        # Find HDFC holding (account 0, security 0) — has buy + sell
        hdfc_results = [
            h for h in result.holdings if h.security.key == sample_securities[0].key
        ]
        assert len(hdfc_results) == 1
        assert hdfc_results[0].xirr is not None  # Should compute (has transactions)

        # Find ICICI holding (account 1, security 1) — has only buy
        icici_results = [
            h for h in result.holdings if h.security.key == sample_securities[1].key
        ]
        assert len(icici_results) == 1
        assert icici_results[0].xirr is not None  # Should compute (single purchase)

    def test_no_holdings_returns_empty(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_prices,
    ):
        """Returns empty PerformanceResult when there are no holdings."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_performance(queries=())

        assert result.holdings == []
        assert result.totals.total_current_value == Decimal("0")
        assert result.totals.total_invested == Decimal("0")
        assert result.totals.total_gains == Decimal("0")
        assert result.totals.gains_percentage is None

    def test_xirr_none_when_computation_fails(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_prices,
    ):
        """XIRR is None when the solver fails (e.g. zero-amount transactions)."""
        txn = Transaction(
            transaction_date=datetime.date(2024, 1, 15),
            type=TransactionType.PURCHASE,
            description="Zero amount purchase",
            amount=Decimal("0.00"),
            units=Decimal("100.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        )
        session.add(txn)
        session.commit()

        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_performance(queries=())

        assert result.totals.total_current_value > Decimal("0")
        # Portfolio XIRR should be None (zero-amount flows)
        assert result.totals.xirr is None
        # Per-holding XIRR should also be None for this holding
        hdfc_results = [
            h for h in result.holdings if h.security.key == sample_securities[0].key
        ]
        assert len(hdfc_results) == 1
        assert hdfc_results[0].xirr is None

    def test_limit_and_offset(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Limit and offset control which holdings are returned."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_performance(queries=(), limit=2, offset=0)

        assert len(result.holdings) == 2


class TestGetSummary:
    """Tests for get_summary function."""

    def test_basic_summary(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Basic summary returns expected structure with populated data."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_summary(queries=())

        assert isinstance(result, SummaryResult)
        assert result.metrics.total_current_value > 0
        assert result.metrics.total_invested is not None
        assert result.metrics.total_invested > 0
        assert len(result.top_holdings) > 0
        assert len(result.allocation) > 0
        assert result.as_of is not None

    def test_top_n_limits_holdings(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """top_n controls the number of returned top holdings."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result_one = get_summary(queries=(), top_n=1)

        assert len(result_one.top_holdings) == 1

        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result_all = get_summary(queries=(), top_n=100)

        # Fixtures produce 3 active holdings (TCS has 0 balance)
        assert len(result_all.top_holdings) == 3

    def test_top_holdings_sorted_by_value(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Top holdings are sorted by current_value descending."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_summary(queries=())

        values = [h.current_value for h in result.top_holdings]
        assert values == sorted(values, reverse=True)

    def test_empty_portfolio(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_prices,
    ):
        """Summary with no transactions yields empty holdings and zero values."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_summary(queries=())

        assert len(result.top_holdings) == 0
        assert result.metrics.total_current_value == 0
        assert result.as_of is None

    def test_allocation_included(
        self,
        session,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Allocation entries have security_category attributes."""
        with patch("niveshpy.services.report.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = session
            mock_get_session.return_value.__exit__.return_value = None

            result = get_summary(queries=())

        assert len(result.allocation) > 0
        for entry in result.allocation:
            assert hasattr(entry, "security_category")
            assert isinstance(entry.security_category, SecurityCategory)

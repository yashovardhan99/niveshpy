"""Tests for report service."""

import datetime
from collections.abc import Sequence
from decimal import Decimal

import pytest

from niveshpy.domain.services import LotAccountingService
from niveshpy.exceptions import InvalidInputError, OperationError
from niveshpy.models.account import AccountCreate, AccountPublic
from niveshpy.models.price import PriceCreate, PricePublic
from niveshpy.models.report import (
    Allocation,
    Holding,
    PerformanceHolding,
    SummaryResult,
)
from niveshpy.models.security import SecurityCategory, SecurityPublic, SecurityType
from niveshpy.models.transaction import (
    TransactionCreate,
    TransactionPublic,
    TransactionType,
)
from niveshpy.services.report_service import ReportService
from tests.services.conftest import (
    MockAccountRepository,
    MockPriceRepository,
    MockSecurityRepository,
    MockTransactionRepository,
)


@pytest.fixture
def account_repository():
    """Fixture for AccountRepository."""
    return MockAccountRepository()


@pytest.fixture
def security_repository():
    """Fixture for SecurityRepository."""
    return MockSecurityRepository()


@pytest.fixture
def transaction_repository(account_repository, security_repository, price_repository):
    """Fixture for TransactionRepository."""
    return MockTransactionRepository(
        account_repository, security_repository, price_repository
    )


@pytest.fixture
def price_repository(security_repository):
    """Fixture for PriceRepository."""
    return MockPriceRepository(security_repository)


@pytest.fixture
def lot_accounting_service():
    """Fixture for LotAccountingService."""
    return LotAccountingService()


@pytest.fixture
def report_service(
    account_repository,
    security_repository,
    transaction_repository,
    price_repository,
    lot_accounting_service,
):
    """Fixture for ReportService."""
    return ReportService(
        account_repository=account_repository,
        security_repository=security_repository,
        transaction_repository=transaction_repository,
        price_repository=price_repository,
        lot_accounting_service=lot_accounting_service,
    )


@pytest.fixture
def sample_accounts(
    account_repository: MockAccountRepository,
) -> Sequence[AccountPublic]:
    """Create sample accounts for testing."""
    accounts = [
        AccountCreate(name="Savings Account", institution="HDFC Bank"),
        AccountCreate(name="Investment Account", institution="ICICI"),
        AccountCreate(name="Pension Account", institution="SBI"),
    ]
    account_repository.insert_multiple_accounts(accounts)
    return account_repository.find_accounts([])


@pytest.fixture
def sample_securities(
    security_repository: MockSecurityRepository,
) -> list[SecurityPublic]:
    """Create sample securities for testing."""
    securities = [
        SecurityPublic(
            key="123456",
            name="HDFC Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.datetime.now(),
        ),
        SecurityPublic(
            key="234567",
            name="ICICI Liquid Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.DEBT,
            properties={},
            created=datetime.datetime.now(),
        ),
        SecurityPublic(
            key="RELI",
            name="Reliance Industries",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.datetime.now(),
        ),
        SecurityPublic(
            key="TCS",
            name="TCS Limited",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
            properties={},
            created=datetime.datetime.now(),
        ),
    ]
    security_repository.insert_multiple_securities(securities)
    return security_repository.find_securities([])


@pytest.fixture
def sample_transactions(
    transaction_repository: MockTransactionRepository,
    sample_accounts: Sequence[AccountPublic],
    sample_securities: list[SecurityPublic],
) -> Sequence[TransactionPublic]:
    """Create sample transactions for testing."""
    transactions = [
        # Account 0 - HDFC Equity Fund: Buy 100, Sell 20 = 80 units
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
            type=TransactionType.SALE,
            description="Sold HDFC Fund",
            amount=Decimal("-2000.00"),
            units=Decimal("-20.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[0].key,
        ),
        # Account 1 - ICICI Liquid Fund: Buy 50 units
        TransactionCreate(
            transaction_date=datetime.date(2024, 3, 10),
            type=TransactionType.PURCHASE,
            description="Purchase ICICI Fund",
            amount=Decimal("5000.00"),
            units=Decimal("50.000"),
            account_id=sample_accounts[1].id,
            security_key=sample_securities[1].key,
        ),
        # Account 0 - Reliance Stock: Buy 25 units
        TransactionCreate(
            transaction_date=datetime.date(2024, 4, 5),
            type=TransactionType.PURCHASE,
            description="Purchase Reliance",
            amount=Decimal("25000.00"),
            units=Decimal("25.000"),
            account_id=sample_accounts[0].id,
            security_key=sample_securities[2].key,
        ),
        # Account 2 - TCS Stock: Buy 10, Sell 10 = 0 units (should be excluded)
        TransactionCreate(
            transaction_date=datetime.date(2024, 5, 1),
            type=TransactionType.PURCHASE,
            description="Purchase TCS",
            amount=Decimal("30000.00"),
            units=Decimal("10.000"),
            account_id=sample_accounts[2].id,
            security_key=sample_securities[3].key,
        ),
        TransactionCreate(
            transaction_date=datetime.date(2024, 5, 15),
            type=TransactionType.SALE,
            description="Sold all TCS",
            amount=Decimal("-32000.00"),
            units=Decimal("-10.000"),
            account_id=sample_accounts[2].id,
            security_key=sample_securities[3].key,
        ),
    ]
    transaction_repository.insert_multiple_transactions(transactions)
    return transaction_repository.find_transactions([])


@pytest.fixture
def sample_prices(
    price_repository: MockPriceRepository,
    sample_securities: list[SecurityPublic],
) -> Sequence[PricePublic]:
    """Create sample prices for testing."""
    prices = [
        # HDFC Equity Fund prices
        PriceCreate(
            security_key=sample_securities[0].key,
            date=datetime.date(2024, 6, 1),
            open=Decimal("105.00"),
            high=Decimal("110.00"),
            low=Decimal("103.00"),
            close=Decimal("108.00"),
        ),
        PriceCreate(
            security_key=sample_securities[0].key,
            date=datetime.date(2024, 6, 15),
            open=Decimal("108.00"),
            high=Decimal("112.00"),
            low=Decimal("107.00"),
            close=Decimal("110.00"),
        ),
        # ICICI Liquid Fund prices
        PriceCreate(
            security_key=sample_securities[1].key,
            date=datetime.date(2024, 6, 1),
            open=Decimal("101.00"),
            high=Decimal("101.50"),
            low=Decimal("100.50"),
            close=Decimal("101.00"),
        ),
        # Reliance Stock prices
        PriceCreate(
            security_key=sample_securities[2].key,
            date=datetime.date(2024, 6, 10),
            open=Decimal("1000.00"),
            high=Decimal("1050.00"),
            low=Decimal("995.00"),
            close=Decimal("1020.00"),
        ),
        # TCS Stock prices (for zero-balance security)
        PriceCreate(
            security_key=sample_securities[3].key,
            date=datetime.date(2024, 6, 1),
            open=Decimal("3000.00"),
            high=Decimal("3100.00"),
            low=Decimal("2950.00"),
            close=Decimal("3050.00"),
        ),
    ]
    for price in prices:
        price_repository.overwrite_price(price)
    return price_repository.find_all_prices([])


class TestGetHoldings:
    """Tests for get_holdings function."""

    def test_get_all_holdings(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting all holdings without filters."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=0)

        # Should return 3 holdings (excluding TCS with 0 balance)
        assert len(holdings) == 3
        assert all(isinstance(h, Holding) for h in holdings)

    def test_get_holdings_correct_values(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings have correct calculated values."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=0)

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
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings with zero or near-zero balance are excluded."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=0)

        # TCS with 0 balance should be excluded
        tcs_holdings = [h for h in holdings if h.security.key == "TCS"]
        assert len(tcs_holdings) == 0

    def test_get_holdings_with_limit(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with limit."""
        holdings = report_service.get_holdings(queries=(), limit=2, offset=0)
        assert len(holdings) == 2

    def test_get_holdings_with_offset(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with offset."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=1)
        assert len(holdings) == 2

    def test_get_holdings_with_limit_and_offset(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with both limit and offset."""
        holdings = report_service.get_holdings(queries=(), limit=1, offset=1)
        assert len(holdings) == 1

    def test_get_holdings_offset_beyond_total(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with offset beyond total count."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=10)
        assert len(holdings) == 0

    def test_get_holdings_with_security_filter(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with security filter."""
        holdings = report_service.get_holdings(queries=("HDFC",), limit=30, offset=0)
        # Should return only HDFC Equity Fund
        assert len(holdings) == 1
        assert holdings[0].security.key == "123456"

    def test_get_holdings_with_account_filter(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with account filter."""
        holdings = report_service.get_holdings(
            queries=("acct:Savings",), limit=30, offset=0
        )
        # Should return holdings from Savings Account (HDFC Fund and Reliance Stock)
        assert len(holdings) == 2
        assert all(h.account.name == "Savings Account" for h in holdings)

    def test_get_holdings_with_security_text_filter(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings filtered by security text (searches type/category/name/key)."""
        holdings = report_service.get_holdings(queries=("STOCK",), limit=30, offset=0)
        # Should return only Reliance (STOCK type, non-zero balance); TCS sold out
        assert len(holdings) == 1
        assert holdings[0].security.type == SecurityType.STOCK

    def test_get_holdings_with_institution_filter(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings filtered by account institution."""
        holdings = report_service.get_holdings(
            queries=("acct:ICICI",), limit=30, offset=0
        )
        # Should return holdings from ICICI account
        assert len(holdings) == 1
        assert holdings[0].account.institution == "ICICI"

    def test_get_holdings_with_multiple_filters(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with multiple query filters (OR semantics across REGEX fields)."""
        holdings = report_service.get_holdings(
            queries=("acct:Savings", "HDFC"), limit=30, offset=0
        )
        # Both filters are REGEX_MATCH so they are OR'd:
        # matches Savings account (HDFC Fund + Reliance) OR matches HDFC security (HDFC Fund)
        # Union = HDFC Fund + Reliance (both from Savings)
        assert len(holdings) == 2

    def test_get_holdings_query_no_matches(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting holdings with query that has no matches."""
        holdings = report_service.get_holdings(
            queries=("NonExistent",), limit=30, offset=0
        )
        assert len(holdings) == 0

    def test_get_holdings_empty_database(self, report_service: ReportService):
        """Test getting holdings when database is empty."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=0)
        assert len(holdings) == 0

    def test_get_holdings_invalid_limit(self, report_service: ReportService):
        """Test that invalid limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be at least 1"):
            report_service.get_holdings(queries=(), limit=0, offset=0)

    def test_get_holdings_negative_limit(self, report_service: ReportService):
        """Test that negative limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be at least 1"):
            report_service.get_holdings(queries=(), limit=-1, offset=0)

    def test_get_holdings_invalid_offset(self, report_service: ReportService):
        """Test that negative offset raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Offset cannot be negative"):
            report_service.get_holdings(queries=(), limit=30, offset=-1)

    def test_get_holdings_uses_latest_price(
        self,
        report_service: ReportService,
        price_repository: MockPriceRepository,
        sample_accounts,
        sample_securities,
        sample_transactions,
    ):
        """Test that holdings use the latest price for each security."""
        for price in [
            PriceCreate(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 1),
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("99.00"),
                close=Decimal("102.00"),
            ),
            PriceCreate(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 15),
                open=Decimal("102.00"),
                high=Decimal("108.00"),
                low=Decimal("101.00"),
                close=Decimal("105.00"),  # Latest price
            ),
            PriceCreate(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 10),
                open=Decimal("101.00"),
                high=Decimal("106.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
            ),
        ]:
            price_repository.overwrite_price(price)

        holdings = report_service.get_holdings(queries=("123456",), limit=30, offset=0)
        assert len(holdings) == 1
        assert holdings[0].amount == Decimal("8400.00")  # 80 units * 105.00
        assert holdings[0].date == datetime.date(2024, 6, 15)

    def test_get_holdings_ordering(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings are ordered by amount desc, then account id, then security key."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=0)
        # Order by amount desc: RELI (25500) > HDFC (8800) > ICICI (5050)
        assert len(holdings) == 3
        assert holdings[0].security.key == "RELI"
        assert holdings[1].security.key == "123456"  # HDFC
        assert holdings[2].security.key == "234567"  # ICICI

    def test_get_holdings_decimal_precision(
        self,
        report_service: ReportService,
        price_repository: MockPriceRepository,
        sample_accounts,
        sample_securities,
        sample_transactions,
    ):
        """Test that holdings maintain correct decimal precision."""
        price_repository.overwrite_price(
            PriceCreate(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 1),
                open=Decimal("105.123456"),
                high=Decimal("110.123456"),
                low=Decimal("103.123456"),
                close=Decimal("108.123456"),
            )
        )
        holdings = report_service.get_holdings(queries=("123456",), limit=30, offset=0)
        assert len(holdings) == 1
        assert holdings[0].units == Decimal("80.000")
        # 80 * 108.123456 = 8649.87648, rounded to 8649.88
        assert holdings[0].amount == Decimal("8649.88")

    def test_get_holdings_invested_amounts(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings include correct invested amounts using FIFO."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=0)

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
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that holdings have correct gains (amount - invested)."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=0)

        # HDFC: amount=8800, invested=8000
        hdfc = next(h for h in holdings if h.security.key == "123456")
        assert hdfc.invested is not None
        assert hdfc.amount - hdfc.invested == Decimal("800.00")

        # ICICI: amount=5050, invested=5000
        icici = next(h for h in holdings if h.security.key == "234567")
        assert icici.invested is not None
        assert icici.amount - icici.invested == Decimal("50.00")

        # Reliance: amount=25500, invested=25000
        reli = next(h for h in holdings if h.security.key == "RELI")
        assert reli.invested is not None
        assert reli.amount - reli.invested == Decimal("500.00")

    def test_get_holdings_invested_consistency(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that invested is present for all holdings with purchase history."""
        holdings = report_service.get_holdings(queries=(), limit=30, offset=0)
        for h in holdings:
            assert h.invested is not None

    def test_get_holdings_raises_when_no_purchase_history(
        self,
        report_service: ReportService,
        transaction_repository: MockTransactionRepository,
        sample_accounts,
        sample_securities,
        sample_prices,
    ):
        """Test that get_holdings raises OperationError when purchase history is incomplete."""
        # Sale before any purchase → FIFO oversell
        transaction_repository.insert_transaction(
            TransactionCreate(
                transaction_date=datetime.date(2024, 1, 15),
                type=TransactionType.SALE,
                description="Mystery sale",
                amount=Decimal("-5000.00"),
                units=Decimal("-50.000"),
                account_id=sample_accounts[0].id,
                security_key=sample_securities[0].key,
            )
        )
        # Also add a purchase so a holding exists (units net > 0)
        transaction_repository.insert_transaction(
            TransactionCreate(
                transaction_date=datetime.date(2024, 2, 1),
                type=TransactionType.PURCHASE,
                description="Buy fund",
                amount=Decimal("10000.00"),
                units=Decimal("100.000"),
                account_id=sample_accounts[0].id,
                security_key=sample_securities[0].key,
            )
        )
        with pytest.raises(OperationError, match="Insufficient purchase history"):
            report_service.get_holdings(queries=(), limit=30, offset=0)


class TestGetAllocation:
    """Tests for get_allocation."""

    def test_get_allocation_by_both(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation grouped by both type and category."""
        allocations = report_service.get_allocation(queries=(), group_by="both")

        assert len(allocations) > 0
        assert all(isinstance(a, Allocation) for a in allocations)
        total_allocation = sum(a.allocation for a in allocations)
        assert abs(total_allocation - Decimal("1.0")) <= Decimal("0.0001")

    def test_get_allocation_by_type(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation grouped by type only."""
        allocations = report_service.get_allocation(queries=(), group_by="type")

        assert len(allocations) > 0
        assert all(isinstance(a, Allocation) for a in allocations)
        total_allocation = sum(a.allocation for a in allocations)
        assert abs(total_allocation - Decimal("1.0")) < Decimal("0.0001")

    def test_get_allocation_by_category(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation grouped by category only."""
        allocations = report_service.get_allocation(queries=(), group_by="category")

        assert len(allocations) > 0
        assert all(isinstance(a, Allocation) for a in allocations)
        total_allocation = sum(a.allocation for a in allocations)
        assert abs(total_allocation - Decimal("1.0")) < Decimal("0.0001")

    def test_get_allocation_correct_values_by_both(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocations have correct calculated values when grouped by both."""
        allocations = report_service.get_allocation(queries=(), group_by="both")

        # HDFC Fund (MUTUAL_FUND, EQUITY): 80 * 110 = 8800
        # ICICI Fund (MUTUAL_FUND, DEBT): 50 * 101 = 5050
        # Reliance (STOCK, EQUITY): 25 * 1020 = 25500
        total_value = Decimal("39350.00")

        for alloc in allocations:
            if (
                alloc.security_type == SecurityType.MUTUAL_FUND
                and alloc.security_category == SecurityCategory.EQUITY
            ):
                assert alloc.amount == Decimal("8800.00")
                assert abs(
                    alloc.allocation - Decimal("8800.00") / total_value
                ) < Decimal("0.0001")
            elif (
                alloc.security_type == SecurityType.MUTUAL_FUND
                and alloc.security_category == SecurityCategory.DEBT
            ):
                assert alloc.amount == Decimal("5050.00")
                assert abs(
                    alloc.allocation - Decimal("5050.00") / total_value
                ) < Decimal("0.0001")
            elif (
                alloc.security_type == SecurityType.STOCK
                and alloc.security_category == SecurityCategory.EQUITY
            ):
                assert alloc.amount == Decimal("25500.00")
                assert abs(
                    alloc.allocation - Decimal("25500.00") / total_value
                ) < Decimal("0.0001")

    def test_get_allocation_by_type_aggregates_correctly(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocation by type aggregates multiple categories correctly."""
        allocations = report_service.get_allocation(queries=(), group_by="type")

        # MUTUAL_FUND: 8800 + 5050 = 13850; STOCK: 25500; Total: 39350
        total_value = Decimal("39350.00")

        for alloc in allocations:
            if alloc.security_type == SecurityType.MUTUAL_FUND:
                assert alloc.amount == Decimal("13850.00")
                assert abs(
                    alloc.allocation - Decimal("13850.00") / total_value
                ) < Decimal("0.0001")
            elif alloc.security_type == SecurityType.STOCK:
                assert alloc.amount == Decimal("25500.00")
                assert abs(
                    alloc.allocation - Decimal("25500.00") / total_value
                ) < Decimal("0.0001")
            else:  # pragma: no cover
                pytest.fail(f"Unexpected security type: {alloc.security_type}")

    def test_get_allocation_by_category_aggregates_correctly(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocation by category aggregates multiple types correctly."""
        allocations = report_service.get_allocation(queries=(), group_by="category")

        # EQUITY: 8800 (MF) + 25500 (STOCK) = 34300; DEBT: 5050; Total: 39350
        total_value = Decimal("39350.00")

        for alloc in allocations:
            if alloc.security_category == SecurityCategory.EQUITY:
                assert alloc.amount == Decimal("34300.00")
                assert abs(
                    alloc.allocation - Decimal("34300.00") / total_value
                ) < Decimal("0.0001")
            elif alloc.security_category == SecurityCategory.DEBT:
                assert alloc.amount == Decimal("5050.00")
                assert abs(
                    alloc.allocation - Decimal("5050.00") / total_value
                ) < Decimal("0.0001")
            else:  # pragma: no cover
                pytest.fail(f"Unexpected security category: {alloc.security_category}")

    def test_get_allocation_with_security_filter(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation with security filter."""
        allocations = report_service.get_allocation(queries=("HDFC",), group_by="both")

        assert len(allocations) == 1
        assert isinstance(allocations[0], Allocation)
        assert allocations[0].allocation == Decimal("1.0000")
        assert allocations[0].security_type == SecurityType.MUTUAL_FUND
        assert allocations[0].security_category == SecurityCategory.EQUITY

    def test_get_allocation_with_account_filter(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation with account filter."""
        allocations = report_service.get_allocation(
            queries=("acct:Savings",), group_by="both"
        )
        # Savings Account: HDFC Fund (MUTUAL_FUND/EQUITY) + Reliance (STOCK/EQUITY)
        assert len(allocations) == 2
        total_alloc = sum(a.allocation for a in allocations)
        assert abs(total_alloc - Decimal("1.0")) < Decimal("0.0001")

    def test_get_allocation_empty_database(self, report_service: ReportService):
        """Test getting allocation when database is empty."""
        allocations = report_service.get_allocation(queries=(), group_by="both")
        assert len(allocations) == 0

    def test_get_allocation_excludes_zero_balance(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocation excludes holdings with zero balance."""
        allocations = report_service.get_allocation(queries=(), group_by="both")

        # TCS (zero balance) should not appear; only Reliance represents STOCK
        for alloc in allocations:
            if alloc.security_type == SecurityType.STOCK:
                assert alloc.amount == Decimal("25500.00")

    def test_get_allocation_ordered_by_amount_desc(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test that allocations are ordered by amount descending."""
        allocations = report_service.get_allocation(queries=(), group_by="both")

        amounts = [a.amount for a in allocations]
        assert amounts == sorted(amounts, reverse=True)

    def test_get_allocation_uses_latest_price(
        self,
        report_service: ReportService,
        price_repository: MockPriceRepository,
        sample_accounts,
        sample_securities,
        sample_transactions,
    ):
        """Test that allocation uses the latest price for each security."""
        for price in [
            PriceCreate(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 1),
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("99.00"),
                close=Decimal("102.00"),
            ),
            PriceCreate(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 15),
                open=Decimal("102.00"),
                high=Decimal("108.00"),
                low=Decimal("101.00"),
                close=Decimal("105.00"),  # Latest
            ),
        ]:
            price_repository.overwrite_price(price)

        allocations = report_service.get_allocation(
            queries=("123456",), group_by="both"
        )
        assert len(allocations) == 1
        assert allocations[0].amount == Decimal("8400.00")  # 80 units * 105.00

    def test_get_allocation_decimal_precision(
        self,
        report_service: ReportService,
        price_repository: MockPriceRepository,
        sample_accounts,
        sample_securities,
        sample_transactions,
    ):
        """Test that allocation maintains correct decimal precision."""
        price_repository.overwrite_price(
            PriceCreate(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 1),
                open=Decimal("105.123456"),
                high=Decimal("110.123456"),
                low=Decimal("103.123456"),
                close=Decimal("108.123456"),
            )
        )
        allocations = report_service.get_allocation(
            queries=("123456",), group_by="both"
        )
        assert len(allocations) == 1
        # 80 * 108.123456 = 8649.87648, rounded to 8649.88
        assert allocations[0].amount == Decimal("8649.88")
        assert allocations[0].allocation == Decimal("1.0000")

    def test_get_allocation_with_multiple_filters(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Test getting allocation with multiple query filters (OR semantics)."""
        allocations = report_service.get_allocation(
            queries=("acct:Savings", "HDFC"), group_by="both"
        )
        # Mixed account+security OR filter: price lookup only applies security portion,
        # so RELI (matches account only) is excluded (no price for it via security filter)
        assert len(allocations) == 1


def _make_holding(
    *,
    amount: str,
    invested: str | None = None,
    key: str = "TEST",
    name: str = "Test Fund",
) -> Holding:
    """Create a Holding object for testing compute_portfolio_totals."""
    account = AccountPublic(
        id=1,
        name="Test",
        institution="Test",
        created_at=datetime.datetime.now(),
        properties={},
    )
    security = SecurityPublic(
        key=key,
        name=name,
        type=SecurityType.MUTUAL_FUND,
        category=SecurityCategory.EQUITY,
        properties={},
        created=datetime.datetime.now(),
    )
    amt = Decimal(amount)
    inv = Decimal(invested) if invested is not None else amt
    return Holding(
        account=account,
        security=security,
        date=datetime.date.today(),
        units=Decimal("100"),
        amount=amt,
        invested=inv,
    )


class TestComputePortfolioTotals:
    """Tests for ReportService._compute_portfolio_totals."""

    @pytest.fixture
    def svc(self, report_service: ReportService) -> ReportService:
        """Return the report_service fixture for use in compute_portfolio_totals tests."""
        return report_service

    def test_basic_totals(self, svc: ReportService):
        """Two holdings with invested amounts produce correct aggregate sums."""
        holdings = [
            _make_holding(amount="15000", invested="10000", key="SEC1"),
            _make_holding(amount="8000", invested="6000", key="SEC2"),
        ]
        result = svc._compute_portfolio_totals(holdings)
        assert result.total_current_value == Decimal("23000.00")
        assert result.total_invested == Decimal("16000.00")
        assert result.total_gains == Decimal("7000.00")
        assert result.last_updated == datetime.date.today()

    def test_none_invested(self, svc: ReportService):
        """Holdings where invested defaults to amount yield zero gains."""
        holdings = [
            _make_holding(amount="15000", key="SEC1"),
            _make_holding(amount="8000", key="SEC2"),
        ]
        result = svc._compute_portfolio_totals(holdings)
        assert result.total_current_value == Decimal("23000.00")
        assert result.total_invested == Decimal("23000.00")
        assert result.total_gains == Decimal("0.00")
        assert result.gains_percentage == Decimal("0.0000")

    def test_mixed_invested(self, svc: ReportService):
        """Mix of holdings with explicit and defaulted invested."""
        holdings = [
            _make_holding(amount="15000", invested="10000", key="SEC1"),
            _make_holding(amount="8000", key="SEC2"),
        ]
        result = svc._compute_portfolio_totals(holdings)
        assert result.total_current_value == Decimal("23000.00")
        assert result.total_invested == Decimal("18000.00")  # 10000 + 8000 (defaulted)
        assert result.total_gains == Decimal("5000.00")

    def test_empty_holdings_raises(self, svc: ReportService):
        """Empty holdings list should raise OperationError."""
        with pytest.raises(OperationError, match="No holdings available"):
            svc._compute_portfolio_totals([])

    def test_zero_invested(self, svc: ReportService):
        """Holdings with 0 invested yield None gains_percentage to avoid div by zero."""
        holdings = [
            _make_holding(amount="5000", invested="0"),
        ]
        result = svc._compute_portfolio_totals(holdings)
        assert result.total_invested == Decimal("0.00")
        assert result.gains_percentage is None

    def test_gains_percentage(self, svc: ReportService):
        """Verify correct fraction calculation: gains / invested."""
        holdings = [
            _make_holding(amount="12000", invested="10000", key="SEC1"),
            _make_holding(amount="5500", invested="5000", key="SEC2"),
        ]
        result = svc._compute_portfolio_totals(holdings)
        # total_current = 17500, total_invested = 15000, gains = 2500
        assert result.gains_percentage == Decimal("0.1667")


class TestGetPerformance:
    """Tests for ReportService.get_performance."""

    def test_returns_holdings_with_xirr(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Returns PerformanceResult with holdings, totals, and portfolio XIRR."""
        result = report_service.get_performance(queries=())

        assert len(result.holdings) == 3
        assert result.totals.total_current_value > Decimal("0")
        assert result.totals.total_invested is not None
        assert result.totals.total_invested > Decimal("0")
        assert result.totals.total_gains is not None
        assert result.totals.gains_percentage is not None
        assert result.totals.xirr is not None

        for h in result.holdings:
            assert isinstance(h, PerformanceHolding)
            assert h.current_value > Decimal("0")

    def test_per_holding_xirr_values(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Each holding gets its own XIRR computed from its own transactions."""
        result = report_service.get_performance(queries=())

        hdfc = next(h for h in result.holdings if h.security.key == "123456")
        assert hdfc.xirr is not None

        icici = next(h for h in result.holdings if h.security.key == "234567")
        assert icici.xirr is not None

    def test_no_holdings_returns_empty(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_prices,
    ):
        """Returns empty PerformanceResult when there are no holdings."""
        result = report_service.get_performance(queries=())

        assert result.holdings == []
        assert result.totals.total_current_value == Decimal("0")
        assert result.totals.total_invested == Decimal("0")
        assert result.totals.total_gains == Decimal("0")
        assert result.totals.gains_percentage is None

    @pytest.mark.filterwarnings(
        "ignore:overflow encountered in scalar divide:RuntimeWarning"
    )
    def test_xirr_none_when_computation_fails(
        self,
        report_service: ReportService,
        transaction_repository: MockTransactionRepository,
        price_repository: MockPriceRepository,
        sample_accounts,
        sample_securities,
    ):
        """XIRR is None when the solver fails (e.g. zero-amount transactions)."""
        price_repository.overwrite_price(
            PriceCreate(
                security_key=sample_securities[0].key,
                date=datetime.date(2024, 6, 15),
                open=Decimal("108.00"),
                high=Decimal("112.00"),
                low=Decimal("107.00"),
                close=Decimal("110.00"),
            )
        )
        transaction_repository.insert_transaction(
            TransactionCreate(
                transaction_date=datetime.date(2024, 1, 15),
                type=TransactionType.PURCHASE,
                description="Zero amount purchase",
                amount=Decimal("0.00"),
                units=Decimal("100.000"),
                account_id=sample_accounts[0].id,
                security_key=sample_securities[0].key,
            )
        )
        result = report_service.get_performance(queries=())

        assert result.totals.total_current_value > Decimal("0")
        assert result.totals.xirr is None

        hdfc = next(h for h in result.holdings if h.security.key == "123456")
        assert hdfc.xirr is None

    def test_limit_and_offset(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Limit and offset control which holdings are returned."""
        result = report_service.get_performance(queries=(), limit=2, offset=0)
        assert len(result.holdings) == 2


class TestGetSummary:
    """Tests for ReportService.get_summary."""

    def test_basic_summary(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Basic summary returns expected structure with populated data."""
        result = report_service.get_summary(queries=())

        assert isinstance(result, SummaryResult)
        assert result.metrics.total_current_value > 0
        assert result.metrics.total_invested is not None
        assert result.metrics.total_invested > 0
        assert len(result.top_holdings) > 0
        assert len(result.allocation) > 0
        assert result.as_of is not None

    def test_top_n_limits_holdings(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """top_n controls the number of returned top holdings."""
        result_one = report_service.get_summary(queries=(), top_n=1)
        assert len(result_one.top_holdings) == 1

        result_all = report_service.get_summary(queries=(), top_n=100)
        # Fixtures produce 3 active holdings (TCS has 0 balance)
        assert len(result_all.top_holdings) == 3

    def test_top_holdings_sorted_by_value(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Top holdings are sorted by current_value descending."""
        result = report_service.get_summary(queries=())

        values = [h.current_value for h in result.top_holdings]
        assert values == sorted(values, reverse=True)

    def test_empty_portfolio(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_prices,
    ):
        """Summary with no transactions yields empty holdings and zero values."""
        result = report_service.get_summary(queries=())

        assert len(result.top_holdings) == 0
        assert result.metrics.total_current_value == 0
        assert result.as_of is None

    def test_allocation_included(
        self,
        report_service: ReportService,
        sample_accounts,
        sample_securities,
        sample_transactions,
        sample_prices,
    ):
        """Allocation entries have security_category attributes."""
        result = report_service.get_summary(queries=())

        assert len(result.allocation) > 0
        for entry in result.allocation:
            assert hasattr(entry, "security_category")
            assert isinstance(entry.security_category, SecurityCategory)

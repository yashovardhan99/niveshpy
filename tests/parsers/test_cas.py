"""Tests for CAS parser."""

import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from niveshpy.exceptions import InvalidInputError, OperationError
from niveshpy.models.account import AccountCreate, AccountPublic
from niveshpy.models.parser import ParserInfo
from niveshpy.models.security import SecurityCategory, SecurityCreate
from niveshpy.models.transaction import TransactionType
from niveshpy.parsers.cas import CASParser, CASParserFactory

# Test constants
TEST_FILE_PATH = "/tmp/test_cas.pdf"  # noqa: S108
TEST_PASSWORD = "secret123"  # noqa: S105
TEST_FOLIO = "1234567890"
TEST_AMC = "Test AMC"
TEST_AMFI_CODE = "120503"
TEST_SCHEME_NAME = "Test Equity Growth Fund"
TEST_ISIN = "INF123456789"


def _make_transaction(
    date: datetime.date = datetime.date(2025, 6, 15),
    type_: str = "PURCHASE",
    description: str = "Purchase - via SIP",
    amount: Decimal = Decimal("5000.00"),
    units: Decimal = Decimal("45.1234"),
) -> MagicMock:
    """Build a mock CAS transaction object."""
    txn = MagicMock()
    txn.date = date
    txn.type = type_
    txn.description = description
    txn.amount = amount
    txn.units = units
    return txn


def _make_scheme(
    amfi: str = TEST_AMFI_CODE,
    scheme: str = TEST_SCHEME_NAME,
    type_: str = "EQUITY",
    isin: str = TEST_ISIN,
    transactions: list | None = None,
) -> MagicMock:
    """Build a mock CAS scheme object."""
    s = MagicMock()
    s.amfi = amfi
    s.scheme = scheme
    s.type = type_
    s.isin = isin
    s.transactions = transactions if transactions is not None else [_make_transaction()]
    return s


def _make_folio(
    folio: str = TEST_FOLIO,
    amc: str = TEST_AMC,
    schemes: list | None = None,
) -> MagicMock:
    """Build a mock CAS folio object."""
    f = MagicMock()
    f.folio = folio
    f.amc = amc
    f.schemes = schemes if schemes is not None else [_make_scheme()]
    return f


def _make_cas_data(
    cas_type: str = "DETAILED",
    from_date: str = "01-Jan-2025",
    to_date: str = "31-Dec-2025",
    folios: list | None = None,
) -> MagicMock:
    """Build a mock CASData object."""
    data = MagicMock()
    data.cas_type = cas_type
    data.statement_period.from_ = from_date
    data.statement_period.to = to_date
    data.folios = folios if folios is not None else [_make_folio()]
    return data


@pytest.fixture
def mock_cas_data():
    """Create a standard mock CASData with one folio, one scheme, one transaction."""
    return _make_cas_data()


@pytest.fixture
def mock_casparser(mock_cas_data):
    """Patch casparser module and return the mock with valid CASData."""
    with patch("niveshpy.parsers.cas.casparser") as mock_module:
        mock_module.read_cas_pdf.return_value = mock_cas_data
        mock_module.CASData = type(mock_cas_data)
        yield mock_module


@pytest.fixture
def parser(mock_casparser):
    """Create a CASParser instance backed by mock casparser."""
    return CASParser(TEST_FILE_PATH, TEST_PASSWORD)


@pytest.fixture
def accounts_for_transactions():
    """Create AccountPublic objects matching the default test folio."""
    return [
        AccountPublic(
            id=1,
            name=TEST_FOLIO,
            institution=TEST_AMC,
            created=datetime.datetime(2025, 1, 1),
            properties={"source": "cas"},
        ),
    ]


# ---------------------------------------------------------------------------
# TestCASParserInit
# ---------------------------------------------------------------------------


class TestCASParserInit:
    """Test CASParser __init__ behaviour."""

    def test_init_with_valid_cas_data(self, mock_casparser):
        """Verify parser initialises without error for valid detailed CASData."""
        parser = CASParser(TEST_FILE_PATH, TEST_PASSWORD)
        assert parser.data is not None

    def test_init_non_cas_data_raises(self):
        """Verify InvalidInputError when casparser returns a non-CASData object."""
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = {"bad": "data"}
            mock_module.CASData = MagicMock  # dict is not a MagicMock instance
            with pytest.raises(InvalidInputError, match="Only CAMS and Kfintech"):
                CASParser(TEST_FILE_PATH)

    def test_init_summary_cas_raises(self):
        """Verify InvalidInputError when CASData has cas_type='SUMMARY'."""
        summary_data = _make_cas_data(cas_type="SUMMARY")
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = summary_data
            mock_module.CASData = type(summary_data)
            with pytest.raises(InvalidInputError, match="Only DETAILED"):
                CASParser(TEST_FILE_PATH)

    def test_init_with_password(self):
        """Verify casparser.read_cas_pdf is called with the provided password."""
        cas_data = _make_cas_data()
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            CASParser(TEST_FILE_PATH, TEST_PASSWORD)
            mock_module.read_cas_pdf.assert_called_once_with(
                TEST_FILE_PATH, TEST_PASSWORD
            )

    def test_init_without_password(self):
        """Verify casparser.read_cas_pdf is called with None when no password given."""
        cas_data = _make_cas_data()
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            CASParser(TEST_FILE_PATH)
            mock_module.read_cas_pdf.assert_called_once_with(TEST_FILE_PATH, None)


# ---------------------------------------------------------------------------
# TestGetDateRange
# ---------------------------------------------------------------------------


class TestGetDateRange:
    """Test CASParser.get_date_range behaviour."""

    def test_valid_date_range(self, parser):
        """Verify correct date parsing from statement_period."""
        start, end = parser.get_date_range()
        assert start == datetime.date(2025, 1, 1)
        assert end == datetime.date(2025, 12, 31)

    def test_invalid_date_format_raises(self, mock_casparser):
        """Verify OperationError for unparseable statement_period dates."""
        bad_data = _make_cas_data(from_date="2025/01/01", to_date="2025/12/31")
        mock_casparser.read_cas_pdf.return_value = bad_data
        mock_casparser.CASData = type(bad_data)

        p = CASParser(TEST_FILE_PATH)
        with pytest.raises(OperationError, match="Failed to parse statement period"):
            p.get_date_range()

    def test_date_range_start_before_end(self, parser):
        """Verify that start date is before end date."""
        start, end = parser.get_date_range()
        assert start < end


# ---------------------------------------------------------------------------
# TestGetAccounts
# ---------------------------------------------------------------------------


class TestGetAccounts:
    """Test CASParser.get_accounts behaviour."""

    def test_returns_account_creates(self, parser):
        """Verify each returned item is an AccountCreate."""
        accounts = parser.get_accounts()
        assert all(isinstance(a, AccountCreate) for a in accounts)

    def test_account_properties(self, parser):
        """Verify AccountCreate fields match folio data."""
        accounts = parser.get_accounts()
        assert len(accounts) == 1
        acc = accounts[0]
        assert acc.name == TEST_FOLIO
        assert acc.institution == TEST_AMC
        assert acc.properties == {"source": "cas"}

    def test_multiple_folios(self):
        """Verify one AccountCreate per folio for multiple folios."""
        folios = [
            _make_folio(folio="F001", amc="AMC A"),
            _make_folio(folio="F002", amc="AMC B"),
            _make_folio(folio="F003", amc="AMC C"),
        ]
        cas_data = _make_cas_data(folios=folios)
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParser(TEST_FILE_PATH)
            accounts = p.get_accounts()

        assert len(accounts) == 3
        assert {a.name for a in accounts} == {"F001", "F002", "F003"}


# ---------------------------------------------------------------------------
# TestGetSecurities
# ---------------------------------------------------------------------------


class TestGetSecurities:
    """Test CASParser.get_securities behaviour."""

    def test_returns_security_creates(self, parser):
        """Verify each yielded item is a SecurityCreate."""
        securities = list(parser.get_securities())
        assert len(securities) == 1
        assert isinstance(securities[0], SecurityCreate)

    def test_deduplicates_by_amfi_code(self):
        """Verify same AMFI code in two folios yields only one SecurityCreate."""
        scheme = _make_scheme(amfi="120503")
        folios = [
            _make_folio(folio="F001", schemes=[scheme]),
            _make_folio(folio="F002", schemes=[_make_scheme(amfi="120503")]),
        ]
        cas_data = _make_cas_data(folios=folios)
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParser(TEST_FILE_PATH)
            securities = list(p.get_securities())

        assert len(securities) == 1
        assert securities[0].key == "120503"

    def test_equity_category_mapping(self, parser):
        """Verify type='EQUITY' maps to SecurityCategory.EQUITY."""
        securities = list(parser.get_securities())
        assert securities[0].category == SecurityCategory.EQUITY

    def test_unknown_type_maps_to_other(self):
        """Verify unrecognised scheme type maps to SecurityCategory.OTHER."""
        scheme = _make_scheme(type_="HYBRID")
        cas_data = _make_cas_data(folios=[_make_folio(schemes=[scheme])])
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParser(TEST_FILE_PATH)
            securities = list(p.get_securities())

        assert securities[0].category == SecurityCategory.OTHER


# ---------------------------------------------------------------------------
# TestGetTransactions
# ---------------------------------------------------------------------------


class TestGetTransactions:
    """Test CASParser.get_transactions behaviour."""

    @pytest.mark.parametrize(
        "txn_type",
        [
            "PURCHASE",
            "PURCHASE_SIP",
            "DIVIDEND_REINVEST",
            "SWITCH_IN",
            "SWITCH_IN_MERGER",
            "REVERSAL",
        ],
    )
    def test_purchase_types_mapped(self, txn_type, accounts_for_transactions):
        """Verify purchase-family types map to TransactionType.PURCHASE."""
        txn = _make_transaction(type_=txn_type)
        cas_data = _make_cas_data(
            folios=[_make_folio(schemes=[_make_scheme(transactions=[txn])])]
        )
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParser(TEST_FILE_PATH)
            transactions = list(p.get_transactions(accounts_for_transactions))

        assert len(transactions) == 1
        assert transactions[0].type == TransactionType.PURCHASE

    @pytest.mark.parametrize(
        "txn_type",
        ["REDEMPTION", "SWITCH_OUT", "SWITCH_OUT_MERGER"],
    )
    def test_sale_types_mapped(self, txn_type, accounts_for_transactions):
        """Verify sale-family types map to TransactionType.SALE."""
        txn = _make_transaction(type_=txn_type)
        cas_data = _make_cas_data(
            folios=[_make_folio(schemes=[_make_scheme(transactions=[txn])])]
        )
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParser(TEST_FILE_PATH)
            transactions = list(p.get_transactions(accounts_for_transactions))

        assert len(transactions) == 1
        assert transactions[0].type == TransactionType.SALE

    def test_unknown_types_skipped(self, accounts_for_transactions):
        """Verify unknown transaction types like STAMP_DUTY are silently skipped."""
        txns = [
            _make_transaction(type_="STAMP_DUTY"),
            _make_transaction(type_="PURCHASE"),
        ]
        cas_data = _make_cas_data(
            folios=[_make_folio(schemes=[_make_scheme(transactions=txns)])]
        )
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParser(TEST_FILE_PATH)
            transactions = list(p.get_transactions(accounts_for_transactions))

        assert len(transactions) == 1
        assert transactions[0].type == TransactionType.PURCHASE

    def test_account_not_found_raises(self):
        """Verify OperationError when folio has no matching account."""
        cas_data = _make_cas_data()
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParser(TEST_FILE_PATH)

            # Provide accounts that don't match the folio
            wrong_accounts = [
                AccountPublic(
                    id=99,
                    name="UNKNOWN",
                    institution="OTHER AMC",
                    created=datetime.datetime(2025, 1, 1),
                    properties={},
                ),
            ]
            with pytest.raises(OperationError, match="Account for folio"):
                list(p.get_transactions(wrong_accounts))

    def test_transaction_properties(self, parser, accounts_for_transactions):
        """Verify transaction properties include source and original_type."""
        transactions = list(parser.get_transactions(accounts_for_transactions))
        assert len(transactions) >= 1
        props = transactions[0].properties
        assert props["source"] == "cas"
        assert props["original_type"] == "PURCHASE"

    def test_yields_generator(self, parser, accounts_for_transactions):
        """Verify get_transactions returns an iterable/generator."""
        result = parser.get_transactions(accounts_for_transactions)
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")


# ---------------------------------------------------------------------------
# TestCASParserFactory
# ---------------------------------------------------------------------------


class TestCASParserFactory:
    """Test CASParserFactory public methods."""

    def test_get_parser_info(self):
        """Verify ParserInfo has correct name, extensions, and password flag."""
        info = CASParserFactory.get_parser_info()
        assert isinstance(info, ParserInfo)
        assert info.name == "CAS Parser"
        assert info.file_extensions == [".pdf"]
        assert info.password_required is True

    def test_create_parser_with_path_object(self):
        """Verify factory accepts a Path object and creates a CASParser."""
        cas_data = _make_cas_data()
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParserFactory.create_parser(Path(TEST_FILE_PATH), TEST_PASSWORD)

        assert isinstance(p, CASParser)
        mock_module.read_cas_pdf.assert_called_once_with(
            Path(TEST_FILE_PATH).as_posix(), TEST_PASSWORD
        )

    def test_create_parser_with_string(self):
        """Verify factory accepts a string path and creates a CASParser."""
        cas_data = _make_cas_data()
        with patch("niveshpy.parsers.cas.casparser") as mock_module:
            mock_module.read_cas_pdf.return_value = cas_data
            mock_module.CASData = type(cas_data)
            p = CASParserFactory.create_parser(TEST_FILE_PATH, TEST_PASSWORD)

        assert isinstance(p, CASParser)
        mock_module.read_cas_pdf.assert_called_once_with(TEST_FILE_PATH, TEST_PASSWORD)

"""Tests for AMFI provider."""

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import requests

from niveshpy.exceptions import NetworkError, OperationError, ResourceNotFoundError
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.providers.amfi import AMFIProvider, AMFIProviderFactory

# Test constants
TEST_AMFI_CODE = "120503"
TEST_DATE = "03-01-2026"
TEST_NAV = "145.7823"


@pytest.fixture(scope="module")
def amfi_provider():
    """Create an AMFIProvider instance for testing."""
    return AMFIProvider()


@pytest.fixture
def mutual_fund_with_amfi_code():
    """Security with amfi_code in properties."""
    return Security(
        key="MF001",
        name="Test Mutual Fund",
        type=SecurityType.MUTUAL_FUND,
        category=SecurityCategory.EQUITY,
        properties={"amfi_code": TEST_AMFI_CODE},
    )


@pytest.fixture
def mutual_fund_with_numeric_key():
    """Security with 6-digit numeric key."""
    return Security(
        key=TEST_AMFI_CODE,
        name="Test Mutual Fund",
        type=SecurityType.MUTUAL_FUND,
        category=SecurityCategory.EQUITY,
    )


@pytest.fixture
def mutual_fund_without_amfi_code():
    """Security without valid AMFI code."""
    return Security(
        key="INVALID",
        name="Test Mutual Fund",
        type=SecurityType.MUTUAL_FUND,
        category=SecurityCategory.EQUITY,
    )


@pytest.fixture
def mock_response():
    """Create a mock Response object."""
    response = MagicMock(spec=requests.Response)
    response.raise_for_status = MagicMock()
    return response


class TestGetPriority:
    """Test get_priority public method."""

    def test_mutual_fund_with_amfi_code_property_returns_priority_10(
        self, amfi_provider, mutual_fund_with_amfi_code
    ):
        """Test that security with amfi_code property gets highest priority."""
        priority = amfi_provider.get_priority(mutual_fund_with_amfi_code)
        assert priority == 10

    def test_mutual_fund_with_amfi_code_as_integer(self, amfi_provider):
        """Test that amfi_code as integer works."""
        security = Security(
            key="MF001",
            name="Test",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            properties={"amfi_code": int(TEST_AMFI_CODE)},
        )
        priority = amfi_provider.get_priority(security)
        assert priority == 10

    def test_mutual_fund_with_6_digit_key_returns_priority_15(
        self, amfi_provider, mutual_fund_with_numeric_key
    ):
        """Test that 6-digit numeric key gets medium priority."""
        priority = amfi_provider.get_priority(mutual_fund_with_numeric_key)
        assert priority == 15

    @pytest.mark.parametrize(
        "security_factory,description",
        [
            (
                lambda: Security(
                    key="AAPL",
                    name="Apple Inc",
                    type=SecurityType.STOCK,
                    category=SecurityCategory.EQUITY,
                ),
                "non_mutual_fund",
            ),
            (
                lambda: Security(
                    key="INVALID",
                    name="Test",
                    type=SecurityType.MUTUAL_FUND,
                    category=SecurityCategory.EQUITY,
                ),
                "no_amfi_code",
            ),
            (
                lambda: Security(
                    key="12345",
                    name="Test",
                    type=SecurityType.MUTUAL_FUND,
                    category=SecurityCategory.EQUITY,
                ),
                "key_too_short",
            ),
            (
                lambda: Security(
                    key="1234567",
                    name="Test",
                    type=SecurityType.MUTUAL_FUND,
                    category=SecurityCategory.EQUITY,
                ),
                "key_too_long",
            ),
            (
                lambda: Security(
                    key="ABC123",
                    name="Test",
                    type=SecurityType.MUTUAL_FUND,
                    category=SecurityCategory.EQUITY,
                ),
                "non_numeric_key",
            ),
            (
                lambda: Security(
                    key="",
                    name="Test",
                    type=SecurityType.MUTUAL_FUND,
                    category=SecurityCategory.EQUITY,
                ),
                "empty_key",
            ),
        ],
        ids=[
            "non_mutual_fund",
            "no_amfi_code",
            "key_too_short",
            "key_too_long",
            "non_numeric_key",
            "empty_key",
        ],
    )
    def test_returns_none_for_invalid_securities(
        self, amfi_provider, security_factory, description
    ):
        """Test that various invalid securities return None priority."""
        security = security_factory()
        priority = amfi_provider.get_priority(security)
        assert priority is None, f"Expected None for {description}"


class TestFetchLatestPrice:
    """Test fetch_latest_price public method."""

    def test_successful_fetch_with_valid_response(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test successful price fetch with valid API response."""
        mock_response.json.return_value = {
            "data": [{"date": TEST_DATE, "nav": TEST_NAV}]
        }

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            price = amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

        assert price.security_key == TEST_AMFI_CODE
        assert price.date == datetime.date(2026, 1, 3)
        assert price.open == Decimal(TEST_NAV)
        assert price.high == Decimal(TEST_NAV)
        assert price.low == Decimal(TEST_NAV)
        assert price.close == Decimal(TEST_NAV)

    def test_fetch_uses_correct_url(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that correct API endpoint is called."""
        mock_response.json.return_value = {
            "data": [{"date": TEST_DATE, "nav": "100.0"}]
        }

        with patch.object(
            amfi_provider.session, "get", return_value=mock_response
        ) as mock_get:
            amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

        expected_url = f"https://api.mfapi.in/mf/{TEST_AMFI_CODE}/latest"
        mock_get.assert_called_once_with(url=expected_url)

    def test_fetch_extracts_amfi_code_from_properties(
        self, amfi_provider, mutual_fund_with_amfi_code, mock_response
    ):
        """Test AMFI code extraction from properties."""
        mock_response.json.return_value = {
            "data": [{"date": TEST_DATE, "nav": "100.0"}]
        }

        with patch.object(
            amfi_provider.session, "get", return_value=mock_response
        ) as mock_get:
            amfi_provider.fetch_latest_price(mutual_fund_with_amfi_code)

        expected_url = f"https://api.mfapi.in/mf/{TEST_AMFI_CODE}/latest"
        mock_get.assert_called_once_with(url=expected_url)

    def test_empty_response_raises_resource_not_found(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that empty data array raises ResourceNotFoundError."""
        mock_response.json.return_value = {"data": []}

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

        assert TEST_AMFI_CODE in str(exc_info.value), "Error should mention AMFI code"
        assert "AMFI returned no price data" in exc_info.value.__notes__[0]

    def test_http_404_raises_resource_not_found(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that 404 HTTP error raises ResourceNotFoundError."""
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=404)
        )

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

        assert TEST_AMFI_CODE in str(exc_info.value), "Error should mention AMFI code"

    def test_http_500_raises_network_error(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that 500 HTTP error raises NetworkError."""
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=500)
        )

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            with pytest.raises(NetworkError, match="HTTP error occurred"):
                amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

    def test_json_decode_error_raises_network_error(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that JSON decode error raises NetworkError."""
        mock_response.json.side_effect = requests.JSONDecodeError("Invalid JSON", "", 0)

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            with pytest.raises(NetworkError, match="Failed to decode JSON"):
                amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

    def test_invalid_decimal_raises_operation_error(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that invalid decimal value raises OperationError."""
        mock_response.json.return_value = {"data": [{"date": TEST_DATE, "nav": "N/A"}]}

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            with pytest.raises(OperationError, match="Failed to parse price data"):
                amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

    def test_invalid_date_format_raises_operation_error(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that invalid date format raises OperationError."""
        mock_response.json.return_value = {
            "data": [{"date": "2026-01-03", "nav": "100.0"}]
        }

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            with pytest.raises(OperationError, match="Failed to parse date"):
                amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

    def test_security_without_amfi_code_raises_error(
        self, amfi_provider, mutual_fund_without_amfi_code
    ):
        """Test that security without valid AMFI code raises ResourceNotFoundError."""
        with pytest.raises(ResourceNotFoundError) as exc_info:
            amfi_provider.fetch_latest_price(mutual_fund_without_amfi_code)

        assert "INVALID" in str(exc_info.value)

    def test_missing_data_key_in_response(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that missing 'data' key results in empty iteration."""
        mock_response.json.return_value = {"status": "success"}

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                amfi_provider.fetch_latest_price(mutual_fund_with_numeric_key)

        assert "AMFI returned no price data" in exc_info.value.__notes__[0]


class TestFetchHistoricalPrices:
    """Test fetch_historical_prices public method."""

    def test_successful_fetch_with_multiple_prices(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test successful historical price fetch with multiple results."""
        mock_response.json.return_value = {
            "data": [
                {"date": TEST_DATE, "nav": "145.78"},
                {"date": "02-01-2026", "nav": "145.12"},
                {"date": "01-01-2026", "nav": "144.89"},
            ]
        }

        start_date = datetime.date(2026, 1, 1)
        end_date = datetime.date(2026, 1, 3)

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            prices = list(
                amfi_provider.fetch_historical_prices(
                    mutual_fund_with_numeric_key, start_date, end_date
                )
            )

        assert len(prices) == 3
        assert prices[0].date == datetime.date(2026, 1, 3)
        assert prices[0].close == Decimal("145.78")
        assert prices[1].date == datetime.date(2026, 1, 2)
        assert prices[2].date == datetime.date(2026, 1, 1)

    def test_fetch_uses_correct_url_and_params(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that correct API endpoint and date params are used."""
        mock_response.json.return_value = {"data": []}

        start_date = datetime.date(2026, 1, 1)
        end_date = datetime.date(2026, 1, 31)

        with patch.object(
            amfi_provider.session, "get", return_value=mock_response
        ) as mock_get:
            list(
                amfi_provider.fetch_historical_prices(
                    mutual_fund_with_numeric_key, start_date, end_date
                )
            )

        mock_get.assert_called_once_with(
            url=f"https://api.mfapi.in/mf/{TEST_AMFI_CODE}",
            params={"startDate": "2026-01-01", "endDate": "2026-01-31"},
        )

    def test_returns_generator(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that method returns an iterable/generator."""
        mock_response.json.return_value = {
            "data": [{"date": "03-01-2026", "nav": "100.0"}]
        }

        start_date = datetime.date(2026, 1, 1)
        end_date = datetime.date(2026, 1, 3)

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            result = amfi_provider.fetch_historical_prices(
                mutual_fund_with_numeric_key, start_date, end_date
            )

        # Verify it's a generator/iterator
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")

    def test_empty_response_yields_nothing(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that empty data array yields no results."""
        mock_response.json.return_value = {"data": []}

        start_date = datetime.date(2026, 1, 1)
        end_date = datetime.date(2026, 1, 3)

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            prices = list(
                amfi_provider.fetch_historical_prices(
                    mutual_fund_with_numeric_key, start_date, end_date
                )
            )

        assert len(prices) == 0

    def test_http_404_raises_resource_not_found(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test that 404 error raises ResourceNotFoundError."""
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=404)
        )

        start_date = datetime.date(2026, 1, 1)
        end_date = datetime.date(2026, 1, 3)

        with patch.object(amfi_provider.session, "get", return_value=mock_response):
            with pytest.raises(ResourceNotFoundError):
                list(
                    amfi_provider.fetch_historical_prices(
                        mutual_fund_with_numeric_key, start_date, end_date
                    )
                )

    def test_same_start_and_end_date(
        self, amfi_provider, mutual_fund_with_numeric_key, mock_response
    ):
        """Test with start and end date being the same."""
        mock_response.json.return_value = {
            "data": [{"date": "15-01-2026", "nav": "100.0"}]
        }

        date_ = datetime.date(2026, 1, 15)

        with patch.object(
            amfi_provider.session, "get", return_value=mock_response
        ) as mock_get:
            list(
                amfi_provider.fetch_historical_prices(
                    mutual_fund_with_numeric_key, date_, date_
                )
            )

        mock_get.assert_called_once_with(
            url=f"https://api.mfapi.in/mf/{TEST_AMFI_CODE}",
            params={"startDate": "2026-01-15", "endDate": "2026-01-15"},
        )

    def test_security_without_amfi_code_raises_error(
        self, amfi_provider, mutual_fund_without_amfi_code
    ):
        """Test that security without valid AMFI code raises ResourceNotFoundError."""
        start_date = datetime.date(2026, 1, 1)
        end_date = datetime.date(2026, 1, 3)

        with pytest.raises(ResourceNotFoundError):
            list(
                amfi_provider.fetch_historical_prices(
                    mutual_fund_without_amfi_code, start_date, end_date
                )
            )


class TestAMFIProviderFactory:
    """Test AMFIProviderFactory public methods."""

    def test_create_provider_returns_amfi_provider_instance(self):
        """Test that create_provider returns an AMFIProvider instance."""
        provider = AMFIProviderFactory.create_provider()
        assert isinstance(provider, AMFIProvider)

    def test_create_provider_returns_new_instance_each_time(self):
        """Test that each call creates a new instance."""
        provider1 = AMFIProviderFactory.create_provider()
        provider2 = AMFIProviderFactory.create_provider()
        assert provider1 is not provider2

    def test_get_provider_info_returns_correct_data(self):
        """Test that get_provider_info returns correct ProviderInfo."""
        info = AMFIProviderFactory.get_provider_info()

        assert info.name == "AMFI"
        assert "AMFI" in info.description
        assert info.supports_historical is True
        assert info.supports_latest is True
        assert info.max_concurrent_requests == 0

    def test_created_provider_has_session(self):
        """Test that created provider has initialized session."""
        provider = AMFIProviderFactory.create_provider()
        assert hasattr(provider, "session")
        assert provider.session is not None
        assert "Accept" in provider.session.headers

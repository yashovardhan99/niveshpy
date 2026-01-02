"""Tests for PriceService."""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from niveshpy.exceptions import InvalidInputError, ResourceNotFoundError
from niveshpy.models.output import ProgressUpdate, Warning
from niveshpy.models.price import Price
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.services.price import PriceService
from niveshpy.services.result import MergeAction

from .price_test_providers import (
    ConfigurableProvider,
    ConfigurableProviderFactory,
    ProviderBehavior,
)


@pytest.fixture
def price_service(session):
    """Create PriceService instance with patched get_session."""
    with patch("niveshpy.services.price.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = session
        mock_get_session.return_value.__exit__.return_value = None
        yield PriceService()


@pytest.fixture
def sample_securities(session):
    """Create sample securities for testing."""
    securities = [
        Security(
            key="SEC001",
            name="Security One",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
        ),
        Security(
            key="SEC002",
            name="Security Two",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        ),
        Security(
            key="SEC003",
            name="Security Three",
            type=SecurityType.BOND,
            category=SecurityCategory.DEBT,
        ),
    ]
    session.add_all(securities)
    session.commit()
    for security in securities:
        session.refresh(security)
    return securities


@pytest.fixture
def sample_prices(session, sample_securities):
    """Create sample prices for testing."""
    prices = [
        # SEC001 - multiple dates
        Price(
            security_key="SEC001",
            date=datetime.date(2024, 1, 1),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("98.00"),
            close=Decimal("103.00"),
        ),
        Price(
            security_key="SEC001",
            date=datetime.date(2024, 1, 2),
            open=Decimal("103.00"),
            high=Decimal("108.00"),
            low=Decimal("102.00"),
            close=Decimal("106.00"),
        ),
        Price(
            security_key="SEC001",
            date=datetime.date(2024, 1, 3),
            open=Decimal("106.00"),
            high=Decimal("110.00"),
            low=Decimal("105.00"),
            close=Decimal("109.00"),
        ),
        # SEC002 - single date
        Price(
            security_key="SEC002",
            date=datetime.date(2024, 1, 1),
            open=Decimal("50.00"),
            high=Decimal("52.00"),
            low=Decimal("49.00"),
            close=Decimal("51.00"),
        ),
        # SEC003 - multiple dates
        Price(
            security_key="SEC003",
            date=datetime.date(2024, 1, 1),
            open=Decimal("200.00"),
            high=Decimal("205.00"),
            low=Decimal("198.00"),
            close=Decimal("203.00"),
        ),
        Price(
            security_key="SEC003",
            date=datetime.date(2024, 1, 2),
            open=Decimal("203.00"),
            high=Decimal("207.00"),
            low=Decimal("201.00"),
            close=Decimal("205.00"),
        ),
    ]
    session.add_all(prices)
    session.commit()
    for price in prices:
        session.refresh(price)
    return prices


class TestListPrices:
    """Tests for list_prices method."""

    def test_list_latest_prices_no_filter(self, price_service, sample_prices):
        """Test listing latest prices for all securities."""
        prices = price_service.list_prices(queries=(), limit=30, offset=0)

        # Should return latest price for each security (3 securities)
        assert len(prices) == 3
        # Verify it's the latest dates
        sec001_price = next(p for p in prices if p.security_key == "SEC001")
        assert sec001_price.date == datetime.date(2024, 1, 3)

    def test_list_prices_with_limit(self, price_service, sample_prices):
        """Test listing prices with limit."""
        prices = price_service.list_prices(queries=(), limit=2, offset=0)

        assert len(prices) == 2

    def test_list_prices_with_offset(self, price_service, sample_prices):
        """Test listing prices with offset."""
        prices = price_service.list_prices(queries=(), limit=30, offset=1)

        assert len(prices) == 2

    def test_list_prices_with_limit_and_offset(self, price_service, sample_prices):
        """Test listing prices with both limit and offset."""
        prices = price_service.list_prices(queries=(), limit=1, offset=1)

        assert len(prices) == 1

    def test_list_prices_offset_beyond_total(self, price_service, sample_prices):
        """Test listing prices with offset beyond total count."""
        prices = price_service.list_prices(queries=(), limit=30, offset=10)

        assert len(prices) == 0

    def test_list_prices_with_security_filter(self, price_service, sample_prices):
        """Test listing prices with security query filter."""
        prices = price_service.list_prices(
            queries=("Security One",), limit=30, offset=0
        )

        assert len(prices) == 1
        assert prices[0].security.name == "Security One"
        assert prices[0].date == datetime.date(2024, 1, 3)  # Latest

    def test_list_prices_with_date_filter(self, price_service, sample_prices):
        """Test listing prices with date filter returns all matching prices."""
        prices = price_service.list_prices(
            queries=("date:2024-01-01",), limit=30, offset=0
        )

        # When date filter is present, should return all prices for that date
        assert len(prices) == 3
        assert all(p.date == datetime.date(2024, 1, 1) for p in prices)

    def test_list_prices_query_no_matches(self, price_service, sample_prices):
        """Test listing prices with query that has no matches."""
        prices = price_service.list_prices(
            queries=("NonExistentSecurity",), limit=30, offset=0
        )

        assert len(prices) == 0

    def test_list_prices_empty_database(self, price_service):
        """Test listing prices when database is empty."""
        prices = price_service.list_prices(queries=(), limit=30, offset=0)

        assert len(prices) == 0

    def test_list_prices_invalid_limit_zero(self, price_service, sample_prices):
        """Test that zero limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be positive"):
            price_service.list_prices(queries=(), limit=0, offset=0)

    def test_list_prices_invalid_limit_negative(self, price_service, sample_prices):
        """Test that negative limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be positive"):
            price_service.list_prices(queries=(), limit=-1, offset=0)

    def test_list_prices_invalid_offset_negative(self, price_service, sample_prices):
        """Test that negative offset raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Offset cannot be negative"):
            price_service.list_prices(queries=(), limit=30, offset=-1)

    def test_list_prices_returns_with_security_relation(
        self, price_service, sample_prices
    ):
        """Test that list_prices returns prices with related security object."""
        prices = price_service.list_prices(queries=(), limit=30, offset=0)

        assert len(prices) > 0
        # Check that security is populated
        assert prices[0].security.key is not None
        assert prices[0].security.name is not None


class TestUpdatePrice:
    """Tests for update_price method."""

    def test_update_price_insert_new(self, price_service, sample_securities):
        """Test inserting a new price."""
        result = price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 2, 1),
            ohlc=(
                Decimal("110.00"),
                Decimal("115.00"),
                Decimal("108.00"),
                Decimal("113.00"),
            ),
            source=None,
        )

        assert result == MergeAction.INSERT

    def test_update_price_update_existing(self, price_service, sample_prices):
        """Test updating an existing price."""
        result = price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 1, 1),
            ohlc=(
                Decimal("120.00"),
                Decimal("125.00"),
                Decimal("118.00"),
                Decimal("123.00"),
            ),
            source=None,
        )

        assert result == MergeAction.UPDATE

    def test_update_price_with_source(self, price_service, sample_securities, session):
        """Test updating price with source metadata."""
        price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 2, 1),
            ohlc=(Decimal("110.00"),),
            source="test_source",
        )

        # Verify the price was saved with source
        price = session.get(Price, ("SEC001", datetime.date(2024, 2, 1)))
        assert price is not None
        assert price.properties == {"source": "test_source"}

    def test_update_price_ohlc_single_value(self, price_service, sample_securities):
        """Test update with single OHLC value (close only)."""
        result = price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 2, 1),
            ohlc=(Decimal("100.00"),),
            source=None,
        )

        assert result == MergeAction.INSERT

    def test_update_price_ohlc_two_values(self, price_service, sample_securities):
        """Test update with two OHLC values (open, close)."""
        result = price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 2, 1),
            ohlc=(Decimal("100.00"), Decimal("105.00")),
            source=None,
        )

        assert result == MergeAction.INSERT

    def test_update_price_ohlc_four_values(self, price_service, sample_securities):
        """Test update with four OHLC values (open, high, low, close)."""
        result = price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 2, 1),
            ohlc=(
                Decimal("100.00"),
                Decimal("110.00"),
                Decimal("95.00"),
                Decimal("105.00"),
            ),
            source=None,
        )

        assert result == MergeAction.INSERT

    def test_update_price_ohlc_invalid_count(self, price_service, sample_securities):
        """Test that invalid OHLC count raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="OHLC must contain 1, 2, or 4"):
            price_service.update_price(
                security_key="SEC001",
                date=datetime.date(2024, 2, 1),
                ohlc=(Decimal("100.00"), Decimal("105.00"), Decimal("110.00")),
                source=None,
            )

    def test_update_price_invalid_security_key(self, price_service):
        """Test that invalid security_key raises ResourceNotFoundError."""
        with pytest.raises(ResourceNotFoundError, match="Security.*INVALID"):
            price_service.update_price(
                security_key="INVALID",
                date=datetime.date(2024, 2, 1),
                ohlc=(Decimal("100.00"),),
                source=None,
            )

    def test_update_price_values_persisted(
        self, price_service, sample_securities, session
    ):
        """Test that price values are correctly persisted."""
        price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 2, 1),
            ohlc=(
                Decimal("100.00"),
                Decimal("110.00"),
                Decimal("95.00"),
                Decimal("105.00"),
            ),
            source=None,
        )

        price = session.get(Price, ("SEC001", datetime.date(2024, 2, 1)))
        assert price is not None
        assert price.open == Decimal("100.00")
        assert price.high == Decimal("110.00")
        assert price.low == Decimal("95.00")
        assert price.close == Decimal("105.00")

    def test_update_price_single_value_expands(
        self, price_service, sample_securities, session
    ):
        """Test that single value expands to all OHLC fields."""
        price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 2, 1),
            ohlc=(Decimal("100.00"),),
            source=None,
        )

        price = session.get(Price, ("SEC001", datetime.date(2024, 2, 1)))
        assert price is not None
        # All values should be the same
        assert price.open == Decimal("100.00")
        assert price.high == Decimal("100.00")
        assert price.low == Decimal("100.00")
        assert price.close == Decimal("100.00")

    def test_update_price_two_values_expands(
        self, price_service, sample_securities, session
    ):
        """Test that two values expand to all OHLC fields."""
        price_service.update_price(
            security_key="SEC001",
            date=datetime.date(2024, 2, 1),
            ohlc=(Decimal("100.00"), Decimal("105.00")),
            source=None,
        )

        price = session.get(Price, ("SEC001", datetime.date(2024, 2, 1)))
        assert price is not None
        assert price.open == Decimal("100.00")
        assert price.high == Decimal("105.00")  # max
        assert price.low == Decimal("100.00")  # min
        assert price.close == Decimal("105.00")


class TestValidateProvider:
    """Tests for validate_provider method."""

    def test_validate_provider_not_found(self, price_service):
        """Test that non-existent provider raises ResourceNotFoundError."""
        with pytest.raises(ResourceNotFoundError, match="Price provider.*nonexistent"):
            price_service.validate_provider("nonexistent")

    @patch("niveshpy.services.price.provider_registry")
    def test_validate_provider_exists(self, mock_registry, price_service):
        """Test that existing provider validates successfully."""
        mock_registry.get_provider.return_value = ConfigurableProvider()

        # Should not raise
        price_service.validate_provider("dummy")

    @patch("niveshpy.services.price.provider_registry")
    def test_validate_provider_discovers_before_checking(
        self, mock_registry, price_service
    ):
        """Test that validate_provider calls discover before checking."""
        mock_registry.get_provider.return_value = ConfigurableProvider()

        price_service.validate_provider("dummy")

        # Should have called discover_installed_providers
        mock_registry.discover_installed_providers.assert_called_once_with(name="dummy")


class TestSyncPrices:
    """Tests for sync_prices method."""

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_basic_flow(
        self, mock_registry, price_service, sample_securities, session
    ):
        """Test basic sync_prices flow with dummy provider."""
        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        # Run sync for one security
        messages = list(
            price_service.sync_prices(
                queries=("Security One",), force=False, provider_key=None
            )
        )

        # Verify we got progress messages
        progress_messages = [m for m in messages if isinstance(m, ProgressUpdate)]
        assert len(progress_messages) > 0

        # Verify prices were saved to database
        prices = session.exec(
            Price.__table__.select().where(Price.security_key == "SEC001")  # type: ignore
        ).all()
        assert len(prices) > 0

        # Verify security metadata was updated
        security = session.get(Security, "SEC001")
        assert "last_price_date" in security.properties
        assert security.properties["price_provider"] == "dummy"

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_multiple_securities(
        self, mock_registry, price_service, sample_securities, session
    ):
        """Test syncing prices for multiple securities."""
        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        list(price_service.sync_prices(queries=(), force=False, provider_key=None))

        # Verify prices were saved for all securities
        for security in sample_securities:
            prices = session.exec(
                Price.__table__.select().where(Price.security_key == security.key)  # type: ignore
            ).all()
            assert len(prices) > 0

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_force_flag(
        self, mock_registry, price_service, sample_securities, session
    ):
        """Test that force flag causes re-fetch from default start date."""
        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        # Set last_price_date to recent date
        security = sample_securities[0]
        security.properties = {"last_price_date": "2025-12-30"}
        session.add(security)
        session.commit()

        # Sync with force=True
        list(
            price_service.sync_prices(
                queries=("Security One",), force=True, provider_key=None
            )
        )

        # Should have fetched prices (even though last_price_date was recent)
        prices = session.exec(
            Price.__table__.select().where(Price.security_key == "SEC001")  # type: ignore
        ).all()
        assert len(prices) > 0

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_no_matching_securities(self, mock_registry, price_service):
        """Test that no matching securities raises ResourceNotFoundError."""
        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        with pytest.raises(ResourceNotFoundError, match="No securities found"):
            list(
                price_service.sync_prices(
                    queries=("NonExistent",), force=False, provider_key=None
                )
            )

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_security_without_provider(
        self, mock_registry, price_service, session
    ):
        """Test that securities without applicable provider generate warnings."""
        # Create a security that won't be supported
        unsupported = Security(
            key="UNSUPPORTED001",
            name="Unsupported Security",
            type=SecurityType.OTHER,
            category=SecurityCategory.OTHER,
        )
        session.add(unsupported)
        session.commit()

        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        messages = list(
            price_service.sync_prices(
                queries=("UNSUPPORTED",), force=False, provider_key=None
            )
        )

        # Should have warning message
        warnings = [m for m in messages if isinstance(m, Warning)]
        assert len(warnings) > 0
        assert "No applicable price provider" in warnings[0].content

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_yields_progress_updates(
        self, mock_registry, price_service, sample_securities
    ):
        """Test that sync_prices yields ProgressUpdate messages."""
        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        messages = list(
            price_service.sync_prices(queries=(), force=False, provider_key=None)
        )

        progress_messages = [m for m in messages if isinstance(m, ProgressUpdate)]

        # Should have progress messages for different stages
        stages = {msg.stage for msg in progress_messages}
        assert "sync.setup.providers" in stages
        assert "sync.setup.securities" in stages
        assert "sync.prices.fetch" in stages
        assert "sync.prices.save" in stages

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_specific_provider(
        self, mock_registry, price_service, sample_securities
    ):
        """Test syncing with a specific provider_key."""
        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        list(price_service.sync_prices(queries=(), force=False, provider_key="dummy"))

        # Should have called discover with specific provider name
        mock_registry.discover_installed_providers.assert_called_with("dummy")

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_metadata_updated(
        self, mock_registry, price_service, sample_securities, session
    ):
        """Test that security metadata is updated after sync."""
        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        list(
            price_service.sync_prices(
                queries=("Security One",), force=False, provider_key=None
            )
        )

        security = session.get(Security, "SEC001")
        assert "last_price_date" in security.properties
        assert "price_provider" in security.properties
        assert security.properties["price_provider"] == "dummy"

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_up_to_date_prices(
        self, mock_registry, price_service, sample_securities, session
    ):
        """Test that sync_prices skips securities with up-to-date prices."""
        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        # Set last_price_date to today
        security = sample_securities[0]
        today = datetime.date.today()
        security.properties = {"last_price_date": today.strftime("%Y-%m-%d")}
        session.add(security)
        session.commit()
        session.refresh(security)

        # Count existing prices before sync
        prices_before = session.exec(
            Price.__table__.select().where(Price.security_key == "SEC001")  # type: ignore
        ).all()
        count_before = len(prices_before)

        # Sync without force flag
        list(
            price_service.sync_prices(
                queries=("Security One",), force=False, provider_key=None
            )
        )

        # Should not fetch new prices (already up to date)
        prices_after = session.exec(
            Price.__table__.select().where(Price.security_key == "SEC001")  # type: ignore
        ).all()
        count_after = len(prices_after)

        # No new prices should have been added
        assert count_after == count_before

        # Verify the property is still set correctly
        session.refresh(security)
        assert security.properties["last_price_date"] == today.strftime("%Y-%m-%d")

    @pytest.mark.parametrize(
        "behavior",
        [
            ProviderBehavior.EMPTY,
            ProviderBehavior.NOT_FOUND,
            ProviderBehavior.OLD_DATA,
        ],
    )
    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_provider_no_prices_saved(
        self,
        mock_registry,
        price_service,
        sample_securities,
        session,
        behavior,
    ):
        """Test handling when provider returns no usable prices.

        Covers: empty results, resource not found, and old data scenarios.
        """
        ConfigurableProviderFactory.configure(behavior=behavior)
        mock_registry.list_providers.return_value = [
            (behavior.value, ConfigurableProviderFactory),
        ]

        list(
            price_service.sync_prices(
                queries=("Security One",), force=False, provider_key=None
            )
        )

        # No prices should be saved for these scenarios
        prices = session.exec(
            Price.__table__.select().where(Price.security_key == "SEC001")  # type: ignore
        ).all()
        assert len(prices) == 0

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_provider_network_error_retries(
        self, mock_registry, price_service, sample_securities, session
    ):
        """Test that network errors trigger retries."""
        provider_instance = ConfigurableProvider(
            behavior=ProviderBehavior.NETWORK_ERROR
        )
        ConfigurableProviderFactory.configure(instance=provider_instance)

        mock_registry.list_providers.return_value = [
            (provider_instance.behavior.value, ConfigurableProviderFactory),
        ]

        list(
            price_service.sync_prices(
                queries=("Security One",), force=False, provider_key=None
            )
        )

        # Should have retried (RETRY_COUNT = 3)
        assert provider_instance.call_count == 3

        # Verify no prices were saved after all retries failed
        prices = session.exec(
            Price.__table__.select().where(Price.security_key == "SEC001")  # type: ignore
        ).all()
        assert len(prices) == 0

    @pytest.mark.parametrize(
        "behavior,exception_type,match_pattern",
        [
            (ProviderBehavior.VALUE_ERROR, "OperationError", None),
            (
                ProviderBehavior.RUNTIME_ERROR,
                "OperationError",
                "unexpected error occurred",
            ),
            (
                ProviderBehavior.NIVESHPY_ERROR,
                "InvalidInputError",
                None,
            ),
        ],
    )
    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_provider_raises_exception(
        self,
        mock_registry,
        price_service,
        sample_securities,
        behavior,
        exception_type,
        match_pattern,
    ):
        """Test handling when provider raises various exceptions.

        Covers: ValueError, RuntimeError wrapped in OperationError, and NiveshPyError subclasses.
        """
        from niveshpy.exceptions import InvalidInputError, OperationError

        ConfigurableProviderFactory.configure(behavior=behavior)
        mock_registry.list_providers.return_value = [
            (behavior.value, ConfigurableProviderFactory),
        ]

        exception_class = (
            InvalidInputError
            if exception_type == "InvalidInputError"
            else OperationError
        )

        if match_pattern:
            with pytest.raises(exception_class, match=match_pattern):
                list(
                    price_service.sync_prices(
                        queries=("Security One",), force=False, provider_key=None
                    )
                )
        else:
            with pytest.raises(exception_class) as exc_info:
                generator = price_service.sync_prices(
                    queries=("Security One",), force=False, provider_key=None
                )
                for _ in generator:
                    pass

            # For NiveshPyError, verify context note was added
            if exception_type == "InvalidInputError":
                assert (
                    "Error occurred while fetching prices for security SEC001"
                    in str(exc_info.value.__notes__)
                )

    @patch("niveshpy.services.price.provider_registry")
    def test_sync_prices_large_batch_insert(
        self, mock_registry, price_service, sample_securities, session
    ):
        """Test batch insert logic with more than 1000 prices."""
        ConfigurableProviderFactory.configure(
            behavior=ProviderBehavior.NORMAL, price_count=1500
        )
        mock_registry.list_providers.return_value = [
            ("large_batch", ConfigurableProviderFactory),
        ]

        list(
            price_service.sync_prices(
                queries=("Security One",), force=True, provider_key=None
            )
        )

        # Verify prices were saved
        prices = session.exec(
            Price.__table__.select().where(Price.security_key == "SEC001")  # type: ignore
        ).all()
        # Should have 1500 prices
        assert len(prices) == 1500

    @patch("niveshpy.services.price.provider_registry")
    @patch("niveshpy.services.price.as_completed")
    @patch("niveshpy.services.price.ThreadPoolExecutor")
    def test_sync_prices_executor_exception(
        self,
        mock_executor_class,
        mock_as_completed,
        mock_registry,
        price_service,
        sample_securities,
    ):
        """Test handling when ThreadPoolExecutor's future raises a plain Exception."""
        from unittest.mock import MagicMock

        from niveshpy.exceptions import OperationError

        ConfigurableProviderFactory.configure(behavior=ProviderBehavior.NORMAL)
        mock_registry.list_providers.return_value = [
            ("dummy", ConfigurableProviderFactory),
        ]

        # Create a mock future that raises a plain Exception (not NiveshPyError)
        mock_future = MagicMock()
        mock_future.result.side_effect = RuntimeError("Executor internal error")

        # Create a mock executor that returns our mock future
        mock_executor = MagicMock()
        mock_executor.__enter__.return_value = mock_executor
        mock_executor.__exit__.return_value = None
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value = mock_executor

        # Make as_completed return our mock future
        mock_as_completed.return_value = [mock_future]

        # Should wrap the RuntimeError in OperationError
        with pytest.raises(OperationError, match="unexpected error occurred"):
            list(
                price_service.sync_prices(
                    queries=("Security One",), force=False, provider_key=None
                )
            )

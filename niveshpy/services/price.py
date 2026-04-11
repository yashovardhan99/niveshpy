"""Service for fetching and processing price data."""

import datetime
import decimal
import heapq
from collections.abc import Generator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from niveshpy.core import providers as provider_registry
from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import (
    get_fields_from_queries,
    get_prepared_filters_from_queries,
)
from niveshpy.domain.repositories import PriceRepository, SecurityRepository
from niveshpy.exceptions import (
    InvalidInputError,
    NetworkError,
    NiveshPyError,
    OperationError,
    ResourceNotFoundError,
)
from niveshpy.models.output import BaseMessage, ProgressUpdate, Warning
from niveshpy.models.price import PriceCreate, PricePublicWithRelations
from niveshpy.models.provider import Provider, ProviderInfo
from niveshpy.models.security import Security


@dataclass(slots=True, frozen=True)
class PriceService:
    """Service for fetching and processing price data."""

    DEFAULT_START_DATE = datetime.date(2000, 1, 1)
    RETRY_COUNT = 3

    price_repository: PriceRepository
    security_repository: SecurityRepository

    def list_prices(
        self,
        queries: tuple[str, ...],
        limit: int = 30,
        offset: int = 0,
    ) -> Sequence[PricePublicWithRelations]:
        """List latest prices for securities matching the queries.

        Args:
            queries: Tuple of query strings to filter securities.
            limit: Maximum number of securities to return.
            offset: Number of securities to skip from the start.
        """
        if limit < 1:
            raise InvalidInputError(limit, "Limit must be positive.")
        if offset < 0:
            raise InvalidInputError(offset, "Offset cannot be negative.")

        filters = get_prepared_filters_from_queries(queries, ast.Field.SECURITY)
        if ast.Field.DATE not in get_fields_from_queries(queries):
            # If no date filter, we only want the latest price per security
            prices = self.price_repository.find_latest_prices(filters, limit, offset)
        else:
            # Otherwise, return all prices matching the filters
            prices = self.price_repository.find_all_prices(filters, limit, offset)

        return [
            PricePublicWithRelations(**price.model_dump(), security=price.security)
            for price in prices
        ]

    def update_price(
        self,
        security_key: str,
        date: datetime.date,
        ohlc: tuple[decimal.Decimal, ...],
        source: str | None = None,
    ) -> None:
        """Update price for a specific security on a given date.

        Args:
            security_key: The key of the security to update.
            date: The date for which to update the price (YYYY-MM-DD).
            ohlc: A tuple containing OHLC values. Can be 1 (close),
                2 (open, close), or 4 (open, high, low, close).
            source: Optional source of the price data.

        Raises:
            InvalidInputError: If the number of OHLC values is not 1, 2
                or 4.
            ResourceNotFoundError: If the specified security does not exist.
        """
        if len(ohlc) not in (1, 2, 4):
            raise InvalidInputError(ohlc, "OHLC must contain 1, 2, or 4 values.")

        price_data = PriceCreate(
            security_key=security_key,
            date=date,
            open=ohlc[0],
            high=max(ohlc) if len(ohlc) < 4 else ohlc[1],
            low=min(ohlc) if len(ohlc) < 4 else ohlc[2],
            close=ohlc[-1],
            properties={"source": source} if source else {},
        )

        self.price_repository.overwrite_price(price_data)

    def validate_provider(self, provider_key: str) -> None:
        """Validate if the given provider key is installed.

        Args:
            provider_key: The key of the price provider to validate.

        Raises:
            ResourceNotFoundError: If the provider is not found.
        """
        # Add logic to check if provider is installed.
        provider_registry.discover_installed_providers(name=provider_key)
        provider = provider_registry.get_provider(provider_key)
        if provider is None:
            raise ResourceNotFoundError("Price provider", provider_key)

    def _initialize_providers(
        self, provider_key: str | None
    ) -> Generator[ProgressUpdate, None, list[tuple[str, ProviderInfo, Provider]]]:
        """Discover and initialize provider instances.

        Args:
            provider_key: Optional specific provider to initialize.

        Yields:
            ProgressUpdate messages during initialization.

        Returns:
            List of tuples containing (provider_key, provider_info, provider_instance).
        """
        yield ProgressUpdate(
            "sync.setup.providers", "Looking for price providers", None, None
        )
        provider_registry.discover_installed_providers(provider_key)
        providers = provider_registry.list_providers()

        yield ProgressUpdate(
            "sync.setup.providers", "Initializing providers", None, len(providers)
        )

        provider_instances: list[tuple[str, ProviderInfo, Provider]] = []
        for i, (key, provider_factory) in enumerate(providers):
            provider_info = provider_factory.get_provider_info()
            provider_instance = provider_factory.create_provider()
            provider_instances.append((key, provider_info, provider_instance))

            yield ProgressUpdate(
                "sync.setup.providers",
                "Initializing providers",
                i + 1,
                len(providers),
            )

        return provider_instances

    def _fetch_securities(self, queries: tuple[str, ...]) -> Sequence[Security]:
        """Fetch securities matching the given queries.

        Args:
            queries: Tuple of query strings to filter securities.

        Returns:
            Sequence of matching securities.

        Raises:
            ResourceNotFoundError: If no securities match the queries.
        """
        filters = get_prepared_filters_from_queries(queries, ast.Field.SECURITY)
        securities = self.security_repository.find_securities(filters)

        if len(securities) == 0:
            raise ResourceNotFoundError(
                "Securities", queries, "No securities found matching the given queries."
            )

        return securities

    def _build_provider_map(
        self,
        securities: Sequence[Security],
        provider_instances: list[tuple[str, ProviderInfo, Provider]],
    ) -> tuple[
        dict[str, list[tuple[int, str, ProviderInfo, Provider]]], list[Security]
    ]:
        """Build provider priority map for each security.

        Args:
            securities: Sequence of securities to map providers for.
            provider_instances: List of available provider instances.

        Yields:
            Warning messages for securities with no applicable providers.
            ProgressUpdate messages during mapping.

        Returns:
            Tuple of (provider_map, securities_with_providers).
        """
        provider_map: dict[str, list[tuple[int, str, ProviderInfo, Provider]]] = {}
        securities_with_providers: list[Security] = []

        for security in securities:
            applicable_providers: list[tuple[int, str, ProviderInfo, Provider]] = []
            for key, provider_info, provider_instance in provider_instances:
                priority = provider_instance.get_priority(security)
                if priority is not None:
                    heapq.heappush(
                        applicable_providers,
                        (priority, key, provider_info, provider_instance),
                    )

            if applicable_providers:
                provider_map[security.key] = applicable_providers
                securities_with_providers.append(security)

        return provider_map, securities_with_providers

    def _fetch_prices_for_security(
        self,
        security: Security,
        providers: list[tuple[int, str, ProviderInfo, Provider]],
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> tuple[list[PriceCreate], str, datetime.date] | None:
        """Fetch prices for a security without writing to database.

        Args:
            security: Security to fetch prices for.
            providers: Priority heap of providers to try.
            start_date: Start date for price data.
            end_date: End date for price data.

        Returns:
            Tuple of (price_list, provider_key, max_date) or None if failed/no data.

        Raises:
            NiveshPyError: For unexpected provider errors.
        """
        while providers:
            _, key, provider_info, provider_instance = heapq.heappop(providers)

            for _ in range(self.RETRY_COUNT):
                try:
                    price_data_iter = provider_instance.fetch_historical_prices(
                        security, start_date, end_date
                    )

                    # Materialize and add metadata
                    prices = [
                        self._add_metadata(price, key) for price in price_data_iter
                    ]

                    if not prices:
                        break  # No data, try next provider

                    max_date = max(p.date for p in prices)

                    if max_date < start_date:
                        break  # Data too old, try next provider

                    return (prices, key, max_date)

                except ResourceNotFoundError as e:
                    e.add_note(
                        f"Provider {provider_info.name} reported resource not found for security {security.key}."
                    )
                    logger.info(
                        "Resource not found from provider %s for security %s",
                        provider_info.name,
                        security.key,
                        exc_info=True,
                    )
                    break  # Try next provider
                except NetworkError:
                    logger.warning(
                        "Network error fetching prices from provider %s for security %s",
                        provider_info.name,
                        security.key,
                        exc_info=True,
                    )
                    continue  # Retry with same provider
                except NiveshPyError:
                    raise
                except Exception as e:
                    raise OperationError(
                        f"An unexpected error occurred while fetching prices from provider {provider_info.name} for security {security.key}."
                    ) from e

        return None  # All providers exhausted

    def sync_prices(
        self, queries: tuple[str, ...], force: bool, provider_key: str | None
    ) -> Generator[BaseMessage, None, None]:
        """Sync prices from installed providers.

        Args:
            queries: Tuple of query strings to filter securities.
            force: Whether to force update even if prices are up-to-date.
            provider_key: Optional specific price provider to use.

        Yields:
            BaseMessage instances indicating progress and warnings.

        Raises:
            NiveshPyError: If any error occurs during the sync process.
        """
        provider_instances = yield from self._initialize_providers(provider_key)
        # Let's fetch all matching securities
        yield ProgressUpdate("sync.setup.securities", "Fetching securities", None, None)

        securities = self._fetch_securities(queries)

        yield ProgressUpdate(
            "sync.setup.securities",
            "Fetched securities",
            None,
            len(securities),
        )

        # Now, for each security, determine which provider to use.
        yield ProgressUpdate(
            "sync.setup.securities",
            "Setting up securities for sync",
            None,
            len(securities),
        )

        provider_map, securities_to_sync = self._build_provider_map(
            securities, provider_instances
        )

        # Yield warnings for securities without providers
        for security in securities:
            if security.key not in provider_map:
                yield Warning(
                    f"No applicable price provider found for security {security.key}."
                )

        yield ProgressUpdate(
            "sync.setup.securities",
            "Setting up securities for sync",
            len(securities_to_sync),
            len(securities),
        )

        # Phase 1: Fetch all prices concurrently (network I/O)
        yield ProgressUpdate(
            "sync.prices.fetch",
            "Fetching prices from providers",
            None,
            None,
        )

        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    self._process_sync, security, provider_map[security.key], force
                ): security
                for security in securities_to_sync
            }

            fetch_results = []
            total_prices = 0

            for future in as_completed(futures):
                security = futures[future]
                try:
                    result = future.result()
                    if result:
                        fetch_results.append(result)
                        total_prices += len(result[1])

                    yield ProgressUpdate(
                        "sync.prices.fetch",
                        "Fetched prices",
                        total_prices,
                        None,
                    )
                except NiveshPyError as e:
                    e.add_note(
                        f"Error occurred while fetching prices for security {security.key}."
                    )
                    raise e
                except Exception as e:
                    raise OperationError(
                        f"An unexpected error occurred while fetching prices for security {security.key}."
                    ) from e

        yield ProgressUpdate(
            "sync.prices.fetch",
            "Fetching prices from providers",
            total_prices,
            total_prices,
        )

        # Phase 2: Write all prices sequentially (no DB locking issues)
        yield ProgressUpdate(
            "sync.prices.save",
            "Saving prices to database",
            None,
            total_prices,
        )

        total_count = 0
        for (
            security,
            prices,
            provider_key,
            max_date,
            start_date,
            end_date,
        ) in fetch_results:
            # Write prices to database
            self.price_repository.replace_prices_in_range(
                security.key, start_date, end_date, prices, batch_size=500
            )

            # Update security metadata
            self.security_repository.update_security_properties(
                security.key,
                ("last_price_date", max_date.strftime("%Y-%m-%d")),
                ("price_provider", provider_key),
            )

            total_count += len(prices)
            yield ProgressUpdate(
                "sync.prices.save",
                "Saving prices to database",
                total_count,
                total_prices,
            )

    def _process_sync(
        self,
        security: Security,
        providers: list[tuple[int, str, ProviderInfo, Provider]],
        force: bool,
    ) -> (
        tuple[
            Security,
            list[PriceCreate],
            str,
            datetime.date,
            datetime.date,
            datetime.date,
        ]
        | None
    ):
        """Determine date range and fetch prices (no DB write).

        Args:
            security: Security to fetch prices for.
            providers: Priority heap of providers to try.
            force: Whether to force update even if prices are up-to-date.

        Returns:
            Tuple of (security, prices, provider_key, max_date, start_date, end_date) or None if skipped.
        """
        # First, find the last date for which we have price data
        last_price = security.properties.get("last_price_date", None)

        if last_price is not None:
            last_price_date = datetime.datetime.strptime(last_price, "%Y-%m-%d").date()
        else:
            # No price data exists, set to a very old date.
            last_price_date = self.DEFAULT_START_DATE

        today = datetime.date.today()
        if last_price_date >= today and not force:
            # Prices are up-to-date
            return None

        if force:
            start_date = self.DEFAULT_START_DATE
        else:
            start_date = last_price_date + datetime.timedelta(days=1)

        end_date = today

        result = self._fetch_prices_for_security(
            security, providers, start_date, end_date
        )

        if result is None:
            return None

        prices, provider_key, max_date = result
        return (security, prices, provider_key, max_date, start_date, end_date)

    def _add_metadata(self, price_data: PriceCreate, source: str) -> PriceCreate:
        """Add source metadata to price data."""
        if "source" not in price_data.properties:
            price_data.properties["source"] = source
        return price_data

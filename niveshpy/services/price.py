"""Service for fetching and processing price data."""

import datetime
import decimal
import heapq
from collections.abc import Generator, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import RootModel
from sqlalchemy.orm import aliased
from sqlmodel import col, delete, func, insert, select, update

from niveshpy.core import providers as provider_registry
from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import (
    get_fields_from_queries,
    get_filters_from_queries,
)
from niveshpy.database import get_session
from niveshpy.exceptions import (
    InvalidInputError,
    NetworkError,
    NiveshPyError,
    OperationError,
    ResourceNotFoundError,
)
from niveshpy.models.output import BaseMessage, ProgressUpdate, Warning
from niveshpy.models.price import (
    PRICE_COLUMN_MAPPING,
    Price,
    PriceCreate,
    PricePublicWithRelations,
)
from niveshpy.models.provider import Provider, ProviderInfo
from niveshpy.models.security import (
    SECURITY_COLUMN_MAPPING,
    Security,
)
from niveshpy.services.result import MergeAction


class PriceService:
    """Service for fetching and processing price data."""

    DEFAULT_START_DATE = datetime.date(2000, 1, 1)
    RETRY_COUNT = 3

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
        where_clause = get_filters_from_queries(
            queries, ast.Field.SECURITY, PRICE_COLUMN_MAPPING
        )
        with get_session() as session:
            if ast.Field.DATE not in get_fields_from_queries(queries):
                # If no date filter, return only the latest price per security
                row_num = (
                    func.row_number()
                    .over(
                        partition_by=Price.security_key, order_by=col(Price.date).desc()
                    )
                    .label("row_num")
                )
                cte = (
                    select(Price, row_num)
                    .join(Security)
                    .where(*where_clause)
                    .cte("cte_1")
                )
                aliased_price = aliased(Price, cte)
                query = (
                    select(aliased_price)
                    .where(cte.c.row_num == 1)
                    .order_by(col(aliased_price.security_key))
                )
            else:
                query = (
                    select(Price)
                    .join(Security)
                    .where(*where_clause)
                    .order_by(col(Price.security_key), col(Price.date).desc())
                )
            prices = session.exec(query.offset(offset).limit(limit)).all()
            return (
                RootModel[Sequence[PricePublicWithRelations]]
                .model_validate(prices)
                .root
            )

    def update_price(
        self,
        security_key: str,
        date: datetime.date,
        ohlc: tuple[decimal.Decimal, ...],
        source: str | None = None,
    ) -> MergeAction:
        """Update price for a specific security on a given date.

        Args:
            security_key: The key of the security to update.
            date: The date for which to update the price (YYYY-MM-DD).
            ohlc: A tuple containing OHLC values. Can be 1 (close), 2 (open, close), or 4 (open, high, low, close).
            source: Optional source of the price data.

        Returns:
            MergeAction containing the result of the upsert operation.
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
        )
        if source:
            price_data = self._add_metadata(price_data, source)

        result: MergeAction

        with get_session() as session:
            # Check if security exists
            security = session.get(Security, security_key)

            if security is None:
                raise ResourceNotFoundError("Security", security_key)

            # Check if price already exists
            existing_price = session.get(Price, (security_key, date))
            if existing_price is None:
                price = Price.model_validate(price_data)
                result = MergeAction.INSERT
            else:
                price = existing_price
                price.open = price_data.open
                price.high = price_data.high
                price.low = price_data.low
                price.close = price_data.close
                price.properties = price_data.properties
                result = MergeAction.UPDATE

            session.add(price)
            session.commit()

        return result

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
        where_clause = get_filters_from_queries(
            queries, ast.Field.SECURITY, SECURITY_COLUMN_MAPPING
        )

        with get_session() as session:
            securities = session.exec(select(Security).where(*where_clause)).all()

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

    def _bulk_insert_prices_streaming(
        self,
        prices: Iterable[PriceCreate],
        security_key: str,
        start_date: datetime.date,
        end_date: datetime.date,
        batch_size: int = 1000,
    ) -> tuple[int, datetime.date | None]:
        """Insert prices in batches while tracking max date.

        Args:
            session: Database session.
            prices: Iterable of price data to insert.
            security_key: Key of the security.
            start_date: Start date for deletion range.
            end_date: End date for deletion range.
            batch_size: Number of prices to insert per batch.

        Returns:
            Tuple of (total_count, max_date).
        """
        with get_session() as session:
            # Delete existing prices in the range first
            delete_stmt = delete(Price).where(
                col(Price.security_key) == security_key,
                col(Price.date) >= start_date,
                col(Price.date) <= end_date,
            )
            session.exec(delete_stmt)

            total_count = 0
            max_date: datetime.date | None = None
            batch: list[dict] = []

            for price_data in prices:
                # Track max date
                if max_date is None or price_data.date > max_date:
                    max_date = price_data.date

                batch.append(Price.model_validate(price_data).model_dump())

                # Insert when batch is full
                if len(batch) >= batch_size:
                    session.exec(insert(Price), params=batch)
                    total_count += len(batch)
                    batch = []

            # Insert remaining items
            if batch:
                session.exec(insert(Price), params=batch)
                total_count += len(batch)

            session.commit()

            return total_count, max_date

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
                    logger.info(
                        f"Network error fetching prices from provider {provider_info.name} for security {security.key}",
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
            count, _ = self._bulk_insert_prices_streaming(
                iter(prices), security.key, start_date, end_date
            )

            # Update security metadata
            security.properties["last_price_date"] = max_date.strftime("%Y-%m-%d")
            security.properties["price_provider"] = provider_key

            with get_session() as session:
                update_stmt = (
                    update(Security)
                    .where(col(Security.key) == security.key)
                    .values(properties=security.properties)
                )
                session.exec(update_stmt)
                session.commit()

            total_count += count
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

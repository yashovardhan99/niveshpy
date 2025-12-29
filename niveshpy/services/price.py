"""Service for fetching and processing price data."""

import datetime
import decimal
import heapq
import itertools
from collections.abc import Generator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import RootModel
from sqlalchemy.orm import aliased
from sqlmodel import delete, func, insert, select, update

from niveshpy.core import providers as provider_registry
from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import (
    get_fields_from_queries,
    get_filters_from_queries,
)
from niveshpy.database import get_session
from niveshpy.exceptions import (
    InvalidSecurityError,
    NiveshPyError,
    NiveshPySystemError,
    NiveshPyUserError,
    PriceNotFoundError,
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
            raise ValueError("Limit must be positive.")
        where_clause = get_filters_from_queries(
            queries, ast.Field.SECURITY, PRICE_COLUMN_MAPPING
        )
        with get_session() as session:
            if ast.Field.DATE not in get_fields_from_queries(queries):
                # If no date filter, return only the latest price per security
                row_num = (
                    func.row_number()
                    .over(partition_by=Price.security_key, order_by=Price.date.desc())  # type: ignore[attr-defined]
                    .label("row_num")
                )
                cte = (
                    select(Price, row_num)
                    .join(Security)
                    .where(*where_clause)
                    .cte("cte_1")
                )
                aliased_price = aliased(Price, cte)
                query = select(aliased_price).where(cte.c.row_num == 1)
            else:
                query = select(Price).join(Security).where(*where_clause)
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
            raise NiveshPyUserError("OHLC must contain 1, 2, or 4 values.")

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
                raise NiveshPyUserError(
                    f"Security with key {security_key} does not exist."
                )

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
            NiveshPyUserError: If the provider is not found.
        """
        # Add logic to check if provider is installed.
        provider_registry.discover_installed_providers(name=provider_key)
        provider = provider_registry.get_provider(provider_key)
        if provider is None:
            raise NiveshPyUserError(f"Price provider '{provider_key}' is not found.")

    def sync_prices(
        self, queries: tuple[str, ...], force: bool, provider_key: str | None
    ) -> Generator[BaseMessage, None, None]:
        """Sync prices from installed providers.

        Args:
            queries: Tuple of query strings to filter securities.
            force: Whether to force update even if prices are up-to-date.
            provider_key: Optional specific price provider to use.
        """
        # First, let's refresh the list of installed providers
        yield ProgressUpdate(
            "sync.setup.providers", "Looking for price providers", None, None
        )
        provider_registry.discover_installed_providers(provider_key)
        providers = provider_registry.list_providers()

        # Instantiate provider instances
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

        # Let's fetch all matching securities
        yield ProgressUpdate("sync.setup.securities", "Fetching securities", None, None)

        where_clause = get_filters_from_queries(
            queries, ast.Field.SECURITY, SECURITY_COLUMN_MAPPING
        )

        with get_session() as session:
            securities = session.exec(select(Security).where(*where_clause)).all()

        yield ProgressUpdate(
            "sync.setup.securities",
            "Fetched securities",
            None,
            len(securities),
        )

        if len(securities) == 0:
            raise NiveshPyUserError("No securities found matching the given queries.")

        # Now, for each security, determine which provider to use.
        provider_map: dict[str, list[tuple[int, str, ProviderInfo, Provider]]] = {}
        yield ProgressUpdate(
            "sync.setup.securities",
            "Setting up securities for sync",
            None,
            len(securities),
        )

        securities_setup, securities_process = itertools.tee(securities, 2)

        for i, security in enumerate(securities_setup):
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
            else:
                yield Warning(
                    f"No applicable price provider found for security {security.key}."
                )

            yield ProgressUpdate(
                "sync.setup.securities",
                "Setting up securities for sync",
                i + 1,
                len(securities),
            )

        # Now, process syncing prices for each security using ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            futures = []
            for security in securities_process:
                if security.key in provider_map:
                    futures.append(
                        executor.submit(
                            self._process_sync,
                            security,
                            provider_map[security.key],
                            force=force,
                        )
                    )

            count = 0
            for i, future in enumerate(as_completed(futures)):
                try:
                    count += future.result() or 0
                    yield ProgressUpdate(
                        "sync.prices",
                        f"Loaded {count} prices",
                        i + 1,
                        len(futures),
                    )
                except NiveshPyError as e:
                    raise e
                except Exception as e:
                    raise NiveshPySystemError(
                        "An unexpected error occurred during price sync."
                    ) from e

    def _process_sync(
        self,
        security: Security,
        providers: list[tuple[int, str, ProviderInfo, Provider]],
        force: bool,
    ) -> int | None:
        """Process sync for a single security with given providers."""
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

        result: int | None = None

        while providers and (result is None or result == 0):
            _, key, provider_info, provider_instance = heapq.heappop(providers)
            for _ in range(
                self.RETRY_COUNT
            ):  # Retry up to RETRY_COUNT times per provider
                try:
                    price_data_iter = provider_instance.fetch_historical_prices(
                        security, start_date, end_date
                    )

                    data_checker, price_data_iter = itertools.tee(price_data_iter, 2)

                    max_date = max(
                        (price_data.date for price_data in data_checker), default=None
                    )

                    if max_date is None or max_date < start_date:
                        # No data retrieved from this provider
                        break

                    price_data_iter = map(
                        self._add_metadata, price_data_iter, itertools.repeat(key)
                    )

                    # Delete any previous prices in the date range and insert new prices

                    with get_session() as session:
                        delete_stmt = delete(Price).where(
                            Price.security_key == security.key,  # type: ignore
                            Price.date >= start_date,  # type: ignore
                            Price.date <= end_date,  # type: ignore
                        )
                        session.exec(delete_stmt)

                        prices = [
                            Price.model_validate(price).model_dump()
                            for price in price_data_iter
                        ]

                        session.exec(insert(Price), params=prices)
                        session.commit()

                    # Only update metadata after successful save
                    security.properties["last_price_date"] = max_date.strftime(
                        "%Y-%m-%d"
                    )
                    security.properties["price_provider"] = key

                    # Successfully fetched prices
                    result = len(prices)
                    break

                except InvalidSecurityError:
                    break  # Try next provider TODO: Add blacklist mechanism
                except PriceNotFoundError as e:
                    if not e.should_retry:
                        break  # Do not retry, try next provider
                    else:
                        continue  # Retry with the same provider
                except NiveshPyError:
                    raise
                except Exception as e:
                    logger.info(
                        f"Error fetching prices from provider {provider_info.name} for security {security.key}",
                        exc_info=True,
                    )
                    raise NiveshPySystemError(
                        f"An unexpected error occurred while fetching prices from provider {provider_info.name} for security {security.key}."
                    ) from e

        # Also update the security metadata in the database
        update_stmt = (
            update(Security)
            .where(Security.key == security.key)  # type: ignore
            .values(properties=security.properties)
        )
        with get_session() as session:
            session.exec(update_stmt)
            session.commit()

        return result

    def _add_metadata(self, price_data: PriceCreate, source: str) -> PriceCreate:
        """Add source metadata to price data."""
        if "source" not in price_data.properties:
            price_data.properties["source"] = source
        return price_data

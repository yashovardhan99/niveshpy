"""Repository implementation for managing price data using SQLite."""

import datetime
import sys
from collections.abc import Iterable, Sequence
from itertools import islice

from attrs import evolve, frozen

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.core.query.prepare import get_fields_from_filters
from niveshpy.domain.repositories import SecurityRepository
from niveshpy.domain.repositories.price_repository import PriceFetchProfile
from niveshpy.exceptions import IntegrityError, InvalidInputError, ResourceNotFoundError
from niveshpy.infrastructure.sqlite.converters import get_converter
from niveshpy.infrastructure.sqlite.query import (
    PRICE_COLUMNS,
    PRICE_CREATE_COLUMNS,
    Col,
    Delete,
    Fn,
    Insert,
    Query,
)
from niveshpy.infrastructure.sqlite.query_filters import generate_query_from_filters
from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase
from niveshpy.models.price import PriceCreate, PricePublic

if sys.version_info >= (3, 12):
    from itertools import batched
else:

    def batched(iterable, n):
        """Collect data into batches of a specified size."""
        if n < 1:
            raise ValueError("n must be at least one")
        iterator = iter(iterable)
        while batch := tuple(islice(iterator, n)):
            yield batch


@frozen
class SqlitePriceRepository:
    """SQLite-based repository implementation for managing price data.

    Attributes:
        database: The SqliteDatabase instance used for database operations.
        security_repository: The SecurityRepository instance used to fetch associated security data.
        price_table_name: The name of the table in the database where price data is stored.
        security_table_name: The name of the table in the database where security data is stored.
    """

    database: SqliteDatabase
    security_repository: SecurityRepository
    price_table_name: str = "price"
    security_table_name: str = "security"

    def _update_prices_with_security(
        self, prices: Sequence[PricePublic]
    ) -> Sequence[PricePublic]:
        """Helper method to update a sequence of PricePublic objects with their associated Security objects.

        Args:
            prices: A sequence of PricePublic objects to update with their associated Security objects.

        Returns:
            A sequence of PricePublic objects with their associated Security objects included.
        """
        price_security_map = {price.security_key: price for price in prices}
        security_keys = tuple(price_security_map.keys())
        securities = self.security_repository.find_securities_by_keys(security_keys)
        security_map = {security.key: security for security in securities}
        updated_prices = []
        for price in prices:
            security = security_map.get(price.security_key)
            if security is None:
                raise ResourceNotFoundError(
                    "Security",
                    price.security_key,
                    "associated with price not found",
                )
            price = evolve(price, security=security)
            updated_prices.append(price)
        return updated_prices

    def get_price_by_key_and_date(
        self,
        security_key: str,
        date: datetime.date,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> PricePublic | None:
        """Fetch a price by its security key and date.

        Args:
            security_key: The key of the security to fetch the price for.
            date: The date for which to fetch the price.
            fetch_profile: The profile determining the level of detail to fetch for the price.

        Returns:
            The PricePublic object if found, otherwise None.
        """
        query = (
            Query()
            .select(*PRICE_COLUMNS, prefix_table=self.price_table_name)
            .from_(self.price_table_name)
            .where(Col("security_key").eq(security_key), Col("date").eq(date))
        )
        price = self.database.select_one(query, cl=PricePublic)

        if price is None:
            return None

        if fetch_profile == PriceFetchProfile.WITH_SECURITY:
            security = self.security_repository.get_security_by_key(security_key)
            if security is None:
                raise ResourceNotFoundError("Security", security_key)
            price = evolve(price, security=security)

        return price

    def find_all_prices(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Sequence[PricePublic]:
        """Find all prices matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of PricePublic objects matching the filters and pagination criteria.
        """
        query = (
            generate_query_from_filters(
                filters,
                {
                    Field.DATE: [Col(self.price_table_name, "date")],
                    Field.SECURITY: [
                        Col(self.price_table_name, "security_key"),
                        Col(self.security_table_name, "name"),
                        Col(self.security_table_name, "type"),
                        Col(self.security_table_name, "category"),
                    ],
                },
            )
            .from_(self.price_table_name)
            .select(*PRICE_COLUMNS, prefix_table=self.price_table_name)
            .order_by(
                f"{self.price_table_name}.security_key",
                f"{self.price_table_name}.date DESC",
            )
        )

        if Field.SECURITY in get_fields_from_filters(filters):
            query = query.join(
                self.security_table_name,
                Col(self.price_table_name, "security_key").eq(
                    Col(self.security_table_name, "key")
                ),
            )

        if limit is not None:
            query = query.limit(limit)
        if offset > 0:
            query = query.offset(offset)

        prices = self.database.select_many(query, cl=PricePublic)

        if fetch_profile == PriceFetchProfile.WITH_SECURITY:
            prices = self._update_prices_with_security(prices)

        return prices

    def find_latest_prices(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Sequence[PricePublic]:
        """Find the latest prices for securities matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of the latest PricePublic objects for securities matching the filters and pagination criteria.
        """
        filters = list(
            filters
        )  # Convert filters to a list to allow multiple iterations

        filter_query: Query = generate_query_from_filters(
            filters,
            {
                Field.SECURITY: [
                    Col(self.price_table_name, "security_key"),
                    Col(self.security_table_name, "name"),
                    Col(self.security_table_name, "type"),
                    Col(self.security_table_name, "category"),
                ]
            },
        )

        cte = (
            filter_query.from_(self.price_table_name)
            .select(
                Col(self.price_table_name, "security_key"),
                Fn("MAX", Col(self.price_table_name, "date")).alias("max_date"),
            )
            .group_by(f"{self.price_table_name}.security_key")
        )

        if filters:
            # Since the only possible filters at this point are on security fields
            cte = cte.join(
                self.security_table_name,
                Col(self.price_table_name, "security_key").eq(
                    Col(self.security_table_name, "key")
                ),
            )

        main_query = (
            Query()
            .with_cte("latest_prices", cte)
            .select(*PRICE_COLUMNS, prefix_table=self.price_table_name)
            .from_(self.price_table_name)
            .join(
                "latest_prices",
                Col(self.price_table_name, "security_key").eq(
                    Col("latest_prices", "security_key")
                ),
                Col(self.price_table_name, "date").eq(Col("latest_prices", "max_date")),
            )
            .order_by(f"{self.price_table_name}.security_key")
        )

        if limit is not None:
            main_query = main_query.limit(limit)
        if offset > 0:
            main_query = main_query.offset(offset)

        prices = self.database.select_many(main_query, cl=PricePublic)

        if fetch_profile == PriceFetchProfile.WITH_SECURITY:
            prices = self._update_prices_with_security(prices)

        return prices

    def overwrite_price(self, price: PriceCreate) -> None:
        """Overwrite an existing price or insert a new one if it doesn't exist.

        Args:
            price: The PriceCreate object containing the price information to overwrite or insert.

        Raises:
            ResourceNotFoundError: If the associated security for the price does not exist in the database.
        """
        c = get_converter()
        values = c.unstructure_attrs_astuple(price)

        stmt = (
            Insert(self.price_table_name)
            .or_replace()
            .columns_(*PRICE_CREATE_COLUMNS)
            .values_(*values)
        )
        try:
            self.database.execute(stmt)
        except IntegrityError as e:
            if "FOREIGN KEY constraint failed" in str(e.__cause__):
                raise ResourceNotFoundError("Security", price.security_key) from e
            else:
                raise

    def replace_prices_in_range(
        self,
        security_key: str,
        start_date: datetime.date,
        end_date: datetime.date,
        new_prices: Sequence[PriceCreate],
        batch_size: int | None = None,
    ) -> None:
        """Replace all prices for a given security within a specified date range with new prices.

        Args:
            security_key: The key of the security for which to replace prices.
            start_date: The start date of the range for which to replace prices (inclusive).
            end_date: The end date of the range for which to replace prices (inclusive).
            new_prices: A sequence of PriceCreate objects containing the new price information to insert.
            batch_size: Optional batch size for processing the replacement in chunks.
                If None, the replacement will be processed in a single batch.

        Raises:
            ResourceNotFoundError: If the given security key does not exist in the database.
            InvalidInputError: If any of the new prices have dates outside the specified date range,
            have a security key that does not match the given security key, or if there are duplicate
            dates in the new prices.
        """
        if start_date > end_date:
            raise InvalidInputError(
                (start_date, end_date),
                "Start date must be less than or equal to end date",
            )

        if batch_size is not None and batch_size < 1:
            raise InvalidInputError(
                batch_size, "Batch size must be at least 1 if specified"
            )

        # Create batches of new prices if batch_size is specified, otherwise use a single batch with all new prices
        batches: Iterable[Sequence[PriceCreate]] = (
            batched(new_prices, batch_size) if batch_size is not None else (new_prices,)
        )
        seen_dates: set[datetime.date] = set()
        """Set to track seen dates for validating that there are no duplicate dates in the new prices."""

        # Validate the batch of new prices before making any changes to the database
        for price in new_prices:
            if price.security_key != security_key:
                raise InvalidInputError(
                    price,
                    f"Price security key {price.security_key} does not match the given security key {security_key}",
                )
            if price.date < start_date or price.date > end_date:
                raise InvalidInputError(
                    price,
                    f"Price date {price.date} is outside the specified date range {start_date} to {end_date}",
                )
            if price.date in seen_dates:
                raise InvalidInputError(
                    price.date, "Duplicate price date found in new prices"
                )
            seen_dates.add(price.date)

            if price.high < max(price.low, price.open, price.close) or price.low > min(
                price.high, price.open, price.close
            ):
                raise InvalidInputError(
                    price,
                    "High price must be greater than or equal to low, open, and close prices, and low price must be less than or equal to high, open, and close prices",
                )

        with self.database.cursor() as cursor:
            delete_stmt = Delete(self.price_table_name).where(
                Col("security_key").eq(security_key),
                Col("date").between(start_date, end_date),
            )
            cursor.execute(str(delete_stmt), delete_stmt.params)

            if len(new_prices) == 0:
                # If there are no new prices to insert, we can return early after deleting the existing prices
                logger.debug(
                    "No new prices to insert for security %s in range %s to %s, so only deleted existing prices",
                    security_key,
                    start_date.isoformat(),
                    end_date.isoformat(),
                )
                return

            # Insert new prices in batches, validating each batch before insertion to ensure data integrity
            c = get_converter()
            for batch in batches:
                tuples = [c.unstructure_attrs_astuple(price) for price in batch]
                stmt = Insert(self.price_table_name).columns_(*PRICE_CREATE_COLUMNS)
                try:
                    cursor.executemany(str(stmt), tuples)
                except IntegrityError as e:
                    if "FOREIGN KEY constraint failed" in str(e.__cause__):
                        raise ResourceNotFoundError("Security", security_key) from e
                    else:
                        raise

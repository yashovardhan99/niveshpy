"""Repository implementation for managing price data using SQLite."""

import datetime
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import islice

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, raiseload, selectinload
from sqlmodel import col, delete, func, insert, select

from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.core.query.prepare import get_fields_from_filters, get_sqlalchemy_filters
from niveshpy.database import get_session
from niveshpy.domain.repositories.price_repository import PriceFetchProfile
from niveshpy.exceptions import DatabaseError, InvalidInputError, ResourceNotFoundError
from niveshpy.models.price import Price, PriceCreate
from niveshpy.models.security import Security

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


@dataclass(slots=True, frozen=True)
class SqlitePriceRepository:
    """SQLite-based repository implementation for managing price data."""

    def get_price_by_key_and_date(
        self,
        security_key: str,
        date: datetime.date,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Price | None:
        """Fetch a price by its security key and date.

        Args:
            security_key: The key of the security to fetch the price for.
            date: The date for which to fetch the price.
            fetch_profile: The profile determining the level of detail to fetch for the price.

        Returns:
            The Price object if found, otherwise None.
        """
        stmt = select(Price).where(
            col(Price.security_key) == security_key,
            col(Price.date) == date,
        )
        if fetch_profile == PriceFetchProfile.WITH_SECURITY:
            stmt = stmt.options(selectinload(Price.security))  # ty:ignore[invalid-argument-type]
        else:
            stmt = stmt.options(raiseload("*"))

        with get_session() as session:
            result = session.exec(stmt).first()
            return result

    def find_all_prices(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Sequence[Price]:
        """Find all prices matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of Price objects matching the filters and pagination criteria.
        """
        where_clauses = get_sqlalchemy_filters(
            filters,
            {
                Field.DATE: [Price.date],
                Field.SECURITY: [
                    Security.key,
                    Security.name,
                    Security.type,
                    Security.category,
                ],
            },
        )
        stmt = select(Price)

        if Field.SECURITY in get_fields_from_filters(filters):
            stmt = stmt.join(Security)
            # If the filters include security fields, we need to eager load the security relationship to avoid N+1 queries
            if fetch_profile == PriceFetchProfile.WITH_SECURITY:
                stmt = stmt.options(contains_eager(Price.security))  # ty:ignore[invalid-argument-type]
        # If the filters don't include security fields but the fetch profile requires security,
        # we can use selectinload to load the related securities in a separate query, which is more efficient than a join in this case
        elif fetch_profile == PriceFetchProfile.WITH_SECURITY:
            stmt = stmt.options(selectinload(Price.security))  # ty:ignore[invalid-argument-type]

        # If the fetch profile is minimal, we can use raiseload to prevent loading any relationships,
        # which can improve performance if we don't need the related data
        if fetch_profile == PriceFetchProfile.MINIMAL:
            stmt = stmt.options(raiseload("*"))

        stmt = stmt.where(*where_clauses).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        with get_session() as session:
            results = session.exec(stmt).all()
            return results

    def find_latest_prices(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Sequence[Price]:
        """Find the latest prices for securities matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of the latest Price objects for securities matching the filters and pagination criteria.
        """
        where_clauses = get_sqlalchemy_filters(
            filters,
            {
                Field.SECURITY: [
                    Security.key,
                    Security.name,
                    Security.type,
                    Security.category,
                ]
            },
        )

        subquery = select(Price.security_key, func.max(Price.date).label("max_date"))

        if filters:
            subquery = subquery.join(Security).where(*where_clauses)
        subquery = subquery.group_by(Price.security_key).subquery("latest_prices")

        stmt = (
            select(Price)
            .join(
                subquery,
                (col(Price.security_key) == subquery.c.security_key)
                & (col(Price.date) == subquery.c.max_date),
            )
            .offset(offset)
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        if fetch_profile == PriceFetchProfile.WITH_SECURITY:
            stmt = stmt.options(selectinload(Price.security))  # ty:ignore[invalid-argument-type]
        else:
            stmt = stmt.options(raiseload("*"))

        with get_session() as session:
            results = session.exec(stmt).all()
            return results

    def overwrite_price(self, price: PriceCreate) -> None:
        """Overwrite an existing price or insert a new one if it doesn't exist.

        Args:
            price: The PriceCreate object containing the price information to overwrite or insert.

        Raises:
            ResourceNotFoundError: If the associated security for the price does not exist in the database.
        """
        stmt = (
            sqlite_insert(Price)
            .values(
                security_key=price.security_key,
                date=price.date,
                open=price.open,
                high=price.high,
                low=price.low,
                close=price.close,
                properties=price.properties,
            )
            .on_conflict_do_update(
                set_={
                    "open": price.open,
                    "high": price.high,
                    "low": price.low,
                    "close": price.close,
                    "properties": price.properties,
                    "created": datetime.datetime.now(),
                },
            )
        )
        with get_session() as session:
            try:
                session.exec(stmt)
                session.commit()
            except IntegrityError as e:
                session.rollback()
                if "FOREIGN KEY constraint failed" in str(e):
                    raise ResourceNotFoundError("Security", price.security_key) from e
                else:
                    raise DatabaseError("Failed to overwrite price") from e

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

        with get_session() as session:
            with session.begin():
                # First, delete existing prices in the specified date range for the given security key
                delete_stmt = delete(Price).where(
                    col(Price.security_key) == security_key,
                    col(Price.date).between(start_date, end_date),
                )
                session.exec(delete_stmt)

                # Then, insert new prices in batches, validating each batch before insertion to ensure data integrity
                for batch in batches:
                    # If validation passes, proceed with inserting new prices
                    price_dicts = [
                        {
                            "security_key": security_key,
                            "date": price.date,
                            "open": price.open,
                            "high": price.high,
                            "low": price.low,
                            "close": price.close,
                            "properties": price.properties,
                            "created": datetime.datetime.now(),
                        }
                        for price in batch
                    ]
                    stmt = insert(Price).values(price_dicts)
                    try:
                        session.exec(stmt)
                    except IntegrityError as e:
                        session.rollback()
                        if "FOREIGN KEY constraint failed" in str(e):
                            raise ResourceNotFoundError("Security", security_key) from e
                        else:
                            raise DatabaseError(
                                "Failed to replace prices in range"
                            ) from e

"""Price repository."""

import datetime
import itertools
from collections.abc import Iterable
from dataclasses import asdict
from typing import Literal, overload

import polars as pl

from niveshpy.core.logging import logger
from niveshpy.db import query
from niveshpy.db.database import Database
from niveshpy.db.query import (
    DEFAULT_QUERY_OPTIONS,
    QueryOptions,
    ast,
    prepare_query_filters,
)
from niveshpy.models.price import PriceDataRead, PriceDataWrite


class PriceRepository:
    """Repository for managing price data."""

    _table_name = "prices"

    _column_mappings = {
        ast.Field.DATE: ["p.price_date"],
        ast.Field.SECURITY: [
            "securities.key",
            "securities.name",
            "securities.type",
            "securities.category",
        ],
    }

    def __init__(self, db: Database):
        """Initialize the PriceRepository with a database connection."""
        self._db = db

    def count_prices(self, options: QueryOptions = DEFAULT_QUERY_OPTIONS) -> int:
        """Count the number of price records matching the query options."""
        has_dates = options.filters is not None and any(
            f.field == ast.Field.DATE for f in options.filters
        )

        if has_dates:
            query = f"""
            SELECT COUNT(*) AS count FROM {self._table_name} p
            INNER JOIN securities ON p.security_key = securities.key
            """
        else:
            query = f"""
            SELECT COUNT(DISTINCT p.security_key) FROM {self._table_name} p
            INNER JOIN securities ON p.security_key = securities.key
            """

        if options.filters:
            filter_query, params = prepare_query_filters(
                options.filters, self._column_mappings
            )
            query += " WHERE " + filter_query
        else:
            params = ()

        query += ";"

        logger.debug("Executing count query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            res = cursor.execute(query, params).fetchone()
            result = res[0] if res else 0

        return result

    @overload
    def search_prices(
        self,
        options: QueryOptions = ...,
        format: Literal[query.ResultFormat.POLARS] = ...,
    ) -> pl.DataFrame: ...

    @overload
    def search_prices(
        self,
        options: QueryOptions = ...,
        format: Literal[query.ResultFormat.LIST] = ...,
    ) -> Iterable[PriceDataRead]: ...

    def search_prices(
        self,
        options: QueryOptions = DEFAULT_QUERY_OPTIONS,
        format: Literal[
            query.ResultFormat.POLARS, query.ResultFormat.LIST
        ] = query.ResultFormat.POLARS,
    ) -> pl.DataFrame | Iterable[PriceDataRead]:
        """Search for price records matching the query options.

        If no date filter is provided, returns the latest price for each security.
        """
        base_query = f"""
        SELECT 
            concat(securities.name, ' (', securities.key, ')') AS security,
            p.price_date AS date, p.open, p.high, p.low, p.close, 
            p.created_at AS created, p.metadata
        FROM {self._table_name} p
        INNER JOIN securities ON p.security_key = securities.key
        """

        params: tuple = ()
        if options.filters:
            filter_query, params = prepare_query_filters(
                options.filters, self._column_mappings
            )
            base_query += " WHERE " + filter_query

        if not options.filters or not any(
            f.field == ast.Field.DATE for f in options.filters
        ):
            base_query += " QUALIFY row_number() OVER (PARTITION BY p.security_key ORDER BY p.price_date DESC) = 1 "

        base_query += " ORDER BY security, p.price_date DESC"

        if options.limit is not None:
            base_query += " LIMIT ?"
            params += (options.limit,)

        base_query += ";"

        logger.debug("Executing search query: %s with params: %s", base_query, params)

        with self._db.cursor() as cursor:
            cursor.execute(base_query, params)
            if format == query.ResultFormat.POLARS:
                return cursor.pl()
            else:
                return itertools.starmap(PriceDataRead, cursor.fetchall())

    def upsert_price(self, price_data: PriceDataWrite) -> str | None:
        """Insert or update a price record in the database."""
        query = f"""
                INSERT OR REPLACE INTO {self._table_name} 
                (security_key, price_date, open, high, low, close, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING merge_action;
                """
        with self._db.cursor() as cursor:
            cursor.begin()
            cursor.execute(
                query,
                (
                    price_data.security_key,
                    price_data.date,
                    price_data.open,
                    price_data.high,
                    price_data.low,
                    price_data.close,
                    price_data.metadata,
                ),
            )
            result = cursor.fetchone()
            cursor.commit()
        return result[0] if result else None

    def overwrite_prices(
        self,
        security_key: str,
        start_date: datetime.date,
        end_date: datetime.date,
        prices: Iterable[PriceDataWrite],
    ) -> int:
        """Overwrite price data for a security within a date range.

        Deletes existing prices in the specified date range and inserts new prices.

        Args:
            security_key: The security key to overwrite prices for.
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
            prices: An iterable of PriceDataWrite objects to insert.

        Returns:
            The number of price records inserted.
        """
        delete_query = f"""
        DELETE FROM {self._table_name}
        WHERE security_key = ? AND price_date BETWEEN ? AND ?;
        """

        insert_query = f"""
        INSERT INTO {self._table_name} 
        (security_key, price_date, open, high, low, close, metadata)
        SELECT * FROM new_prices;
        """

        with self._db.cursor() as cursor:
            cursor.begin()
            # Delete existing prices in the date range
            cursor.execute(delete_query, (security_key, start_date, end_date))

            df_prices = pl.from_dicts(asdict(p) for p in prices)
            cursor.register("new_prices", df_prices)
            # Insert new prices
            cursor.execute(insert_query)

            result = cursor.rowcount

            cursor.commit()
            return result

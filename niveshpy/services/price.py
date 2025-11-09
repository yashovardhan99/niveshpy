"""Service for fetching and processing price data."""

import datetime
import decimal

import polars as pl

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_filters_from_queries
from niveshpy.db import query
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.exceptions import NiveshPySystemError, NiveshPyUserError
from niveshpy.models.price import PriceDataWrite
from niveshpy.services.result import ListResult, MergeAction


class PriceService:
    """Service for fetching and processing price data."""

    def __init__(self, repos: RepositoryContainer):
        """Initialize the PriceService with a RepositoryContainer."""
        self._repos = repos

    def list_prices(
        self, queries: tuple[str, ...], limit: int
    ) -> ListResult[pl.DataFrame]:
        """List latest prices for securities matching the queries.

        Args:
            queries: Tuple of query strings to filter securities.
            limit: Maximum number of securities to return.
        """
        if limit < 1:
            raise ValueError("Limit must be positive.")
        filters = get_filters_from_queries(queries, default_field=ast.Field.SECURITY)
        logger.debug("Prepared filters for price listing: %s", filters)

        options = query.QueryOptions(filters=filters, limit=limit)

        N = self._repos.price.count_prices(options)
        if N == 0:
            return ListResult(pl.DataFrame(), 0)

        res = self._repos.price.search_prices(options, query.ResultFormat.POLARS)
        return ListResult(res, N)

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

        # Check if security exists
        security = self._repos.security.get_security(security_key)
        if security is None:
            raise NiveshPyUserError(f"Security with key {security_key} does not exist.")

        price_data = PriceDataWrite(
            security_key=security_key,
            date=date,
            open=ohlc[0],
            high=max(ohlc) if len(ohlc) < 4 else ohlc[1],
            low=min(ohlc) if len(ohlc) < 4 else ohlc[2],
            close=ohlc[-1],
        )
        if source:
            price_data.metadata["source"] = source

        result = self._repos.price.upsert_price(price_data)

        if result is None:
            raise NiveshPySystemError(
                f"Failed to update price for security {security_key} on {date}."
            )

        return MergeAction(result)

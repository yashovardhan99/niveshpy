"""Service for fetching and processing price data."""

import polars as pl

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_filters_from_queries
from niveshpy.db import query
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.services.result import ListResult


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

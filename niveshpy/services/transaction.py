"""Transaction service for managing user transactions."""

from collections.abc import Iterable
import itertools
from niveshpy.core.query import ast
from niveshpy.core.query.parser import QueryParser
from niveshpy.core.query.prepare import prepare_filters
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.db.query import QueryOptions, ResultFormat
from niveshpy.db.repositories import RepositoryContainer
import polars as pl
from niveshpy.core.logging import logger
from niveshpy.services.result import ListResult


class TransactionService:
    """Service handler for the transactions command group."""

    def __init__(self, repos: RepositoryContainer):
        """Initialize the TransactionService with repositories."""
        self._repos = repos

    def list_transactions(
        self,
        queries: tuple[str, ...],
        limit: int = 30,
    ) -> ListResult[pl.DataFrame]:
        """List transactions matching the query."""
        if limit < 1:
            logger.debug("Received non-positive limit: %d", limit)
            raise ValueError("Limit must be positive.")

        stripped_queries = map(str.strip, queries)
        lexers = map(QueryLexer, stripped_queries)
        parsers = map(QueryParser, lexers)
        filters: Iterable[ast.FilterNode] = itertools.chain.from_iterable(
            map(QueryParser.parse, parsers)
        )
        filters = prepare_filters(filters, ast.Field.SECURITY)
        logger.debug("Prepared filters: %s", filters)

        options = QueryOptions(
            filters=filters,
            limit=limit,
        )

        N = self._repos.transaction.count_transactions(options)
        if N == 0:
            return ListResult(pl.DataFrame(), 0)

        res = self._repos.transaction.search_transactions(
            options, ResultFormat.POLARS
        ).select(
            pl.col("id"),
            pl.col("transaction_date").alias("date"),
            pl.col("type"),
            pl.col("description"),
            pl.col("amount"),
            pl.col("units"),
            pl.concat_str(
                [
                    pl.col("security_name"),
                    pl.lit(" ("),
                    pl.col("security_key"),
                    pl.lit(")"),
                ]
            ).alias("security"),
            pl.concat_str(
                [
                    pl.col("account_name"),
                    pl.lit(" ("),
                    pl.col("account_institution"),
                    pl.lit(")"),
                ]
            ).alias("account"),
            pl.col("created_at").alias("created"),
            pl.col("metadata"),
        )
        return ListResult(res, N)

    # def get_transactions(self):
    #     """Get all transactions."""
    #     return self._repos.transaction.get_transactions()

    # def add_transactions(self, transactions):
    #     """Add new transactions."""
    #     return self._repos.transaction.add_transactions(transactions)

    # def get_accounts(self):
    #     """Get all accounts."""
    #     return self._repos.account.get_accounts()

    # def get_securities(self):
    #     """Get all securities."""
    #     return self._repos.security.get_securities()

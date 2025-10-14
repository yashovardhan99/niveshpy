"""Account service for managing investment accounts."""

from collections.abc import Iterable
import itertools
from niveshpy.core.query import ast
from niveshpy.core.query.parser import QueryParser
from niveshpy.core.query.prepare import prepare_filters
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.db.query import QueryOptions, ResultFormat
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.models.account import AccountRead, AccountWrite
import polars as pl
from niveshpy.core.logging import logger
from niveshpy.services.result import ListResult


class AccountService:
    """Service handler for the accounts command group."""

    def __init__(self, repos: RepositoryContainer):
        """Initialize the AccountService with repositories."""
        self._repos = repos

    def list_accounts(
        self, queries: tuple[str, ...], limit: int = 30
    ) -> ListResult[pl.DataFrame]:
        """List accounts, optionally filtered by a query string."""
        stripped_queries = map(str.strip, queries)
        lexers = map(QueryLexer, stripped_queries)
        parsers = map(QueryParser, lexers)
        filters: Iterable[ast.FilterNode] = itertools.chain.from_iterable(
            map(QueryParser.parse, parsers)
        )
        filters = prepare_filters(filters, ast.Field.ACCOUNT)
        logger.debug("Prepared filters: %s", filters)

        options = QueryOptions(filters=filters, limit=limit)

        if limit < 1:
            logger.debug("Received non-positive limit: %d", limit)
            raise ValueError("Limit must be positive.")

        N = self._repos.account.count_accounts(options)
        if N == 0:
            return ListResult(pl.DataFrame(), 0)

        res = self._repos.account.search_accounts(options, format=ResultFormat.POLARS)
        return ListResult(res, N)

    def get_accounts(self) -> pl.DataFrame:
        """Get all accounts."""
        return self._repos.account.get_accounts()

    def add_accounts(self, accounts: Iterable[AccountWrite]) -> Iterable[AccountRead]:
        """Add new accounts."""
        return self._repos.account.add_accounts(accounts)

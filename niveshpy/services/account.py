"""Account service for managing investment accounts."""

from collections.abc import Iterable
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
        self, query: str = "", limit: int = 30
    ) -> ListResult[pl.DataFrame]:
        """List accounts, optionally filtered by a query string."""
        options = QueryOptions(text_query=query.strip() if query else None, limit=limit)

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

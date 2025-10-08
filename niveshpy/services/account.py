"""Account service for managing investment accounts."""

from collections.abc import Iterable
from niveshpy.db.repositories import Repositories
from niveshpy.models.account import AccountRead, AccountWrite
import polars as pl


class AccountService:
    """Service handler for the accounts command group."""

    def __init__(self, repos: Repositories):
        """Initialize the AccountService with repositories."""
        self._repos = repos

    def get_accounts(self) -> pl.DataFrame:
        """Get all accounts."""
        return self._repos.account.get_accounts()

    def add_accounts(self, accounts: Iterable[AccountWrite]) -> Iterable[AccountRead]:
        """Add new accounts."""
        return self._repos.account.add_accounts(accounts)

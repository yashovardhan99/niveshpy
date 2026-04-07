"""Account repository for NiveshPy."""

from collections.abc import Iterable, Sequence
from typing import Protocol

from niveshpy.core.query.ast import FilterNode
from niveshpy.models.account import Account, AccountCreate


class AccountRepository(Protocol):
    """Repository interface for retrieving and managing accounts."""

    def get_account_by_id(self, account_id: int) -> Account | None:
        """Fetch an account by its ID.

        Args:
            account_id: The ID of the account to fetch.

        Returns:
            The Account object if found, otherwise None.
        """

    def get_account_by_name_and_institution(
        self, name: str, institution: str
    ) -> Account | None:
        """Fetch an account by its name and institution.

        Args:
            name: The name of the account.
            institution: The institution associated with the account.

        Returns:
            The Account object if found, otherwise None.
        """

    def find_accounts(
        self, filters: Iterable[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[Account]:
        """Find accounts matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter accounts.
            limit: Optional maximum number of accounts to return.
            offset: Optional number of accounts to skip before returning results.

        Returns:
            A sequence of Account objects matching the filters and pagination criteria.
        """

    def find_accounts_by_name_and_institutions(
        self, names: Sequence[str], institutions: Sequence[str]
    ) -> Sequence[Account]:
        """Find accounts matching the given name-institution pairs.

        Args:
            names: A sequence of account names to search for.
            institutions: A sequence of institution names to search for.

        Returns:
            A sequence of Account objects matching the given name-institution pairs.
        """

    def insert_account(self, account: AccountCreate) -> int | None:
        """Insert a new account.

        Args:
            account: An AccountCreate object containing the details of the account to insert.

        Returns:
            The ID of the newly inserted account if successful, otherwise None.
        """

    def insert_multiple_accounts(self, accounts: Iterable[AccountCreate]) -> int:
        """Insert multiple accounts.

        Args:
            accounts: An iterable of AccountCreate objects to insert.

        Returns:
            The number of accounts successfully inserted.
        """

    def delete_account_by_id(self, account_id: int) -> bool:
        """Delete an account by its ID.

        Args:
            account_id: The ID of the account to delete.

        Returns:
            True if the account was successfully deleted, False otherwise.
        """

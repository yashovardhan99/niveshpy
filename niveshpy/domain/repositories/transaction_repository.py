"""Transaction repository for NiveshPy."""

from collections.abc import Iterable, Sequence
from enum import Enum, auto
from typing import Protocol

from niveshpy.core.query.ast import FilterNode
from niveshpy.models.transaction import Transaction, TransactionCreate


class TransactionFetchProfile(Enum):
    """Enum for defining different fetch profiles for transactions."""

    MINIMAL = auto()
    """Fetch only the basic transaction fields without any related entities."""
    WITH_RELATIONS = auto()
    """Fetch transaction fields along with related entities (e.g., account, security)."""


class TransactionSortOrder(Enum):
    """Enum for defining sorting options for transactions."""

    DATE_ASC_ID_ASC = auto()
    """Sort transactions by date in ascending order and by ID in ascending order."""
    DATE_DESC_ID_DESC = auto()
    """Sort transactions by date in descending order and by ID in descending order."""
    ID_ASC = auto()
    """Sort transactions by ID in ascending order."""
    ID_DESC = auto()
    """Sort transactions by ID in descending order."""


class TransactionRepository(Protocol):
    """Repository interface for retrieving and managing transactions."""

    def get_transaction_by_id(
        self,
        transaction_id: int,
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
    ) -> Transaction | None:
        """Fetch a transaction by its unique ID.

        Args:
            transaction_id: The unique ID of the transaction to fetch.
            fetch_profile: The fetch profile to determine the level of detail to retrieve.

        Returns:
            The Transaction object if found, otherwise None.
        """

    def find_transactions(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
        sort_order: TransactionSortOrder = TransactionSortOrder.DATE_DESC_ID_DESC,
    ) -> Sequence[Transaction]:
        """Find transactions matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter transactions.
            limit: Optional maximum number of transactions to return.
            offset: Optional number of transactions to skip before returning results.
            fetch_profile: The fetch profile to determine the level of detail to retrieve.
            sort_order: The sort order to determine the order of the returned transactions.

        Returns:
            A sequence of Transaction objects matching the filters and pagination criteria.
        """

    def find_transactions_by_ids(self, ids: Sequence[int]) -> Sequence[Transaction]:
        """Find transactions matching the given list of IDs.

        Args:
            ids: A sequence of unique IDs to search for.

        Returns:
            A sequence of Transaction objects matching the given IDs.
        """

    def insert_transaction(self, transaction: TransactionCreate) -> int:
        """Insert a new transaction.

        Args:
            transaction: A TransactionCreate object containing the details of the transaction to insert.

        Returns:
            The unique ID of the newly inserted transaction.
        """

    def insert_multiple_transactions(
        self, transactions: Sequence[TransactionCreate]
    ) -> int:
        """Insert multiple transactions.

        Args:
            transactions: A sequence of TransactionCreate objects to insert.

        Returns:
            The number of transactions successfully inserted.
        """

    def delete_transaction_by_id(self, transaction_id: int) -> bool:
        """Delete a transaction by its ID.

        Args:
            transaction_id: The unique ID of the transaction to delete.

        Returns:
            True if the transaction was deleted successfully, False if no transaction with the given ID was found.
        """

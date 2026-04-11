"""Security repository for NiveshPy."""

from collections.abc import Sequence
from typing import Any, Protocol

from niveshpy.core.query.ast import FilterNode
from niveshpy.models.security import Security, SecurityCreate


class SecurityRepository(Protocol):
    """Repository interface for retrieving and managing securities."""

    def get_security_by_key(self, key: str) -> Security | None:
        """Fetch a security by its unique key.

        Args:
            key: The unique key of the security to fetch.

        Returns:
            The Security object if found, otherwise None.
        """

    def find_securities(
        self, filters: list[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[Security]:
        """Find securities matching the given filters with optional pagination.

        Args:
            filters: A list of FilterNode objects to filter securities.
            limit: Optional maximum number of securities to return.
            offset: Optional number of securities to skip before returning results.

        Returns:
            A sequence of Security objects matching the filters and pagination criteria.
        """

    def find_securities_by_keys(self, keys: Sequence[str]) -> Sequence[Security]:
        """Find securities matching the given list of keys.

        Args:
            keys: A sequence of unique keys to search for.

        Returns:
            A sequence of Security objects matching the given keys.
        """

    def insert_security(self, security: SecurityCreate) -> bool:
        """Insert a new security.

        Args:
            security: A SecurityCreate object containing the details of the security to insert.

        Returns:
            True if the security was inserted successfully, False if a security with the same key already exists.
        """

    def insert_multiple_securities(self, securities: Sequence[SecurityCreate]) -> int:
        """Insert multiple securities.

        Args:
            securities: A sequence of SecurityCreate objects to insert.

        Returns:
            The number of securities successfully inserted.
        """

    def delete_security_by_key(self, key: str) -> bool:
        """Delete a security by its key.

        Args:
            key: The unique key of the security to delete.

        Returns:
            True if the security was deleted successfully, False if no security with the given key was found.
        """

    def update_security_properties(
        self,
        security_key: str,
        *properties: tuple[str, Any],
    ) -> None:
        """Update specific properties of an existing security.

        This method will not delete any existing properties that are not included in the update.
        It will only update the specified properties or add them if they do not already exist.

        Args:
            security_key: The unique key of the security to update.
            properties: A variable number of tuples, each containing a property name and its corresponding new value.

        Raises:
            ResourceNotFoundError: If no security with the given key exists.
        """

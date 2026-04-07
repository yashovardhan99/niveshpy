"""Security service for managing securities."""

from collections.abc import Sequence
from dataclasses import dataclass

from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_prepared_filters_from_queries
from niveshpy.domain.repositories import SecurityRepository
from niveshpy.exceptions import (
    AmbiguousResourceError,
    InvalidInputError,
    QuerySyntaxError,
)
from niveshpy.models.security import (
    Security,
    SecurityCategory,
    SecurityCreate,
    SecurityType,
)


@dataclass(slots=True, frozen=True)
class SecurityService:
    """Service handler for the securities command group.

    Args:
        security_repository (SecurityRepository): Repository for managing securities.
    """

    security_repository: SecurityRepository

    def list_securities(
        self,
        queries: tuple[str, ...],
        limit: int = 30,
        offset: int = 0,
    ) -> Sequence[Security]:
        """List securities matching the query.

        Args:
            queries (tuple[str, ...]): Query strings to filter securities.
            limit (int): Maximum number of securities to return.
            offset (int): Number of securities to skip from the start.

        Returns:
            Sequence[Security]: List of securities matching the query.

        Raises:
            InvalidInputError: If limit is less than 1 or offset is negative.
            QuerySyntaxError: If the query strings cannot be parsed into valid filters.
        """
        if limit < 1:
            raise InvalidInputError(limit, "Limit must be positive.")
        if offset < 0:
            raise InvalidInputError(offset, "Offset cannot be negative.")

        filters = get_prepared_filters_from_queries(queries, ast.Field.SECURITY)
        try:
            securities = self.security_repository.find_securities(
                filters, limit=limit, offset=offset
            )
            return securities
        except QuerySyntaxError as e:
            e.add_note(f"Caused by input queries: {' '.join(queries)}")
            raise QuerySyntaxError(" ".join(queries), e.cause) from e

    def add_security(
        self,
        key: str,
        name: str,
        stype: SecurityType,
        category: SecurityCategory,
        source: str | None = None,
    ) -> bool:
        """Add a single security to the database.

        If a security with the same key already exists, it will be ignored.

        Args:
            key (str): Unique identifier for the security.
            name (str): Name of the security.
            stype (SecurityType): Type of the security.
            category (SecurityCategory): Category of the security.
            source (str | None): Optional source information for the security.

        Returns:
            bool: True if the security was added, False if it already exists.
        """
        if not key.strip() or not name.strip():
            raise InvalidInputError(
                (key, name), "Security key and name cannot be empty."
            )
        # Check if stype is a valid SecurityType enum member
        if not isinstance(stype, SecurityType):
            raise InvalidInputError(stype, f"Invalid security type: {stype}")
        # Check if category is a valid SecurityCategory enum member
        if not isinstance(category, SecurityCategory):
            raise InvalidInputError(category, f"Invalid security category: {category}")
        if source:
            properties = {"source": source}
        else:
            properties = {}

        security = SecurityCreate(
            key=key.strip(),
            name=name.strip(),
            type=stype,
            category=category,
            properties=properties,
        )

        return self.security_repository.insert_security(security)

    def delete_security(self, key: str) -> bool:
        """Delete a security by its key.

        Returns True if a security was deleted, False otherwise.
        """
        if not key.strip():
            raise InvalidInputError(key, "Security key cannot be empty.")
        return self.security_repository.delete_security_by_key(key.strip())

    def resolve_security_key(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> Sequence[Security]:
        """Resolve a security key to a Security object if it exists.

        Args:
            queries (tuple): Tuple of query strings.
            limit (int): Maximum number of candidates to return.
            allow_ambiguous (bool): Whether to allow ambiguous results.

        Returns:
            Sequence[Security]: The resolved security(s).

        Raises:
            InvalidInputError: If no queries are provided and ambiguous results are not allowed.
            AmbiguousResourceError: If a direct match is not found and ambiguous results are not allowed
        """
        # If no queries and ambiguous results not allowed, raise error
        if not queries and not allow_ambiguous:
            raise InvalidInputError(
                queries,
                "No queries provided to resolve security key. Ambiguous results are not allowed.",
            )

        # First, try to find an exact match by key
        security_key = queries[0].strip() if len(queries) == 1 else None

        # If we have a possible security key
        if security_key is not None:
            exact_security = self.security_repository.get_security_by_key(security_key)
            if exact_security is not None:
                return [exact_security]

        # No exact match found by key
        # If ambiguous results are not allowed, raise error
        if not allow_ambiguous:
            raise AmbiguousResourceError("security", " ".join(queries))

        # Perform a text search for candidates
        return self.list_securities(queries, limit=limit)

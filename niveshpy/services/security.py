"""Security service for managing securities."""

from niveshpy.db.query import QueryOptions, ResultFormat
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.models.security import Security, SecurityCategory, SecurityType
import polars as pl
from niveshpy.core.logging import logger

from niveshpy.services.result import (
    InsertResult,
    ListResult,
    MergeAction,
    ResolutionStatus,
    SearchResolution,
)


class SecurityService:
    """Service handler for the securities command group."""

    def __init__(self, repos: RepositoryContainer):
        """Initialize the SecurityService with repositories."""
        self._repos = repos

    def list_securities(
        self,
        query: str | None = None,
        stype: list[SecurityType] | None = None,
        category: list[SecurityCategory] | None = None,
        limit: int = 30,
    ) -> ListResult[pl.DataFrame]:
        """List securities matching the query."""
        filters = {}
        if stype:
            filters["type"] = [SecurityType(s).value for s in stype]
        if category:
            filters["category"] = [SecurityCategory(c).value for c in category]
        options = QueryOptions(
            text_query=query.strip() if query else None,
            filters=filters if filters else None,
            limit=limit,
        )

        if limit < 1:
            logger.debug("Received non-positive limit: %d", limit)
            raise ValueError("Limit must be positive.")

        N = self._repos.security.count_securities(options)
        if N == 0:
            return ListResult(pl.DataFrame(), 0)

        res = self._repos.security.search_securities(options, ResultFormat.POLARS)
        return ListResult(res, N)

    def add_security(
        self, key: str, name: str, stype: SecurityType, category: SecurityCategory
    ) -> InsertResult[Security]:
        """Add a single security to the database."""
        if not key.strip() or not name.strip():
            raise ValueError("Security key and name cannot be empty.")
        if stype not in SecurityType:
            raise ValueError(f"Invalid security type: {stype}")
        if category not in SecurityCategory:
            raise ValueError(f"Invalid security category: {category}")

        security = Security(key.strip(), name.strip(), stype, category)

        action = self._repos.security.insert_single_security(security)
        try:
            if action is None:
                raise ValueError("Action could not be determined.")
            return InsertResult(MergeAction(action), security)
        except ValueError as e:
            raise ValueError("Failed to add security.") from e

    def delete_security(self, key: str) -> bool:
        """Delete a security by its key.

        Returns True if a security was deleted, False otherwise.
        """
        return self._repos.security.delete_security(key.strip()) is not None

    def resolve_security_key(
        self, input: str | None, limit: int, allow_ambiguous: bool = True
    ) -> SearchResolution[Security]:
        """Resolve a security key to a Security object if it exists.

        Logic:
        - If the input is None or empty:
            - If `allow_ambiguous` is False, return NOT_FOUND.
            - Else return AMBIGUOUS with no candidates.
        - If the input matches exactly one security key, return EXACT with that security.
        - Else If `allow_ambiguous` is false, return NOT_FOUND.
        - Else perform a text search:
            - 0 matches: return NOT_FOUND
            - 1 match: return EXACT with that security
            - >1 matches: return AMBIGUOUS with the list of candidates
        """
        if input is None or input.strip() == "":
            if not allow_ambiguous:
                return SearchResolution(ResolutionStatus.NOT_FOUND, original=input)

            # Return top `limit` securities as candidates
            options = QueryOptions(limit=limit)
            res = self._repos.security.search_securities(options, ResultFormat.LIST)
            securities = [Security(*row) for row in res] if res else []
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=securities,
                original=input,
            )

        input = input.strip()

        # First, try to find an exact match by key
        exact_security = self._repos.security.get_security(input)
        if exact_security:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=exact_security,
                original=input,
            )

        if not allow_ambiguous:
            # If ambiguous results are not allowed, return NOT_FOUND
            return SearchResolution(ResolutionStatus.NOT_FOUND, original=input)

        # Perform a text search for candidates
        options = QueryOptions(text_query=input, limit=limit)
        res = self._repos.security.search_securities(options, ResultFormat.LIST)
        if not res:
            return SearchResolution(ResolutionStatus.NOT_FOUND, original=input)
        elif len(res) == 1:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=Security(*res[0]),
                original=input,
            )
        else:
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=[Security(*row) for row in res],
                original=input,
            )
            # If we reach here, it means we have ambiguous results

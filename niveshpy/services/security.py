"""Security service for managing securities."""

import itertools
from collections.abc import Iterable

import polars as pl

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.parser import QueryParser
from niveshpy.core.query.prepare import prepare_filters
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.db.query import QueryOptions, ResultFormat
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.models.security import (
    SecurityCategory,
    SecurityRead,
    SecurityType,
    SecurityWrite,
)
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
        queries: tuple[str, ...],
        limit: int = 30,
    ) -> ListResult[pl.DataFrame]:
        """List securities matching the query."""
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

        if limit < 1:
            logger.debug("Received non-positive limit: %d", limit)
            raise ValueError("Limit must be positive.")

        N = self._repos.security.count_securities(options)
        if N == 0:
            return ListResult(pl.DataFrame(), 0)

        res = self._repos.security.search_securities(
            options, ResultFormat.POLARS
        ).rename({"created_at": "created"})
        return ListResult(res, N)

    def add_security(
        self,
        key: str,
        name: str,
        stype: SecurityType,
        category: SecurityCategory,
        source: str | None = None,
    ) -> InsertResult[SecurityRead]:
        """Add a single security to the database."""
        if not key.strip() or not name.strip():
            raise ValueError("Security key and name cannot be empty.")
        if stype not in SecurityType:
            raise ValueError(f"Invalid security type: {stype}")
        if category not in SecurityCategory:
            raise ValueError(f"Invalid security category: {category}")

        if source:
            metadata = {"source": source}
        else:
            metadata = {}

        security = SecurityWrite(
            key.strip(), name.strip(), stype, category, metadata=metadata
        )

        result = self._repos.security.insert_single_security(security)
        try:
            if result is None:
                raise ValueError("Action could not be determined.")
            return InsertResult(MergeAction(result[0]), result[1])
        except ValueError as e:
            raise ValueError("Failed to add security.") from e

    def delete_security(self, key: str) -> bool:
        """Delete a security by its key.

        Returns True if a security was deleted, False otherwise.
        """
        return self._repos.security.delete_security(key.strip()) is not None

    def resolve_security_key(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> SearchResolution[SecurityRead]:
        """Resolve a security key to a Security object if it exists.

        Logic:
        - If the queries are empty:
            - If `allow_ambiguous` is False, return NOT_FOUND.
            - Else return AMBIGUOUS with no candidates.
        - If the queries match exactly one security key, return EXACT with that security.
        - Else If `allow_ambiguous` is false, return NOT_FOUND.
        - Else perform a text search:
            - 0 matches: return NOT_FOUND
            - 1 match: return EXACT with that security
            - >1 matches: return AMBIGUOUS with the list of candidates
        """
        if not queries:
            if not allow_ambiguous:
                return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)

            # Return top `limit` securities as candidates
            options = QueryOptions(limit=limit)
            res = self._repos.security.search_securities(options, ResultFormat.LIST)
            securities = [SecurityRead(*row) for row in res] if res else []
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=securities,
                queries=queries,
            )

        # First, try to find an exact match by key
        exact_security = self._repos.security.get_security(queries[0].strip())
        if exact_security:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=exact_security,
                queries=queries,
            )

        if not allow_ambiguous:
            # If ambiguous results are not allowed, return NOT_FOUND
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)

        # Perform a text search for candidates
        stripped_queries = map(str.strip, queries)
        lexers = map(QueryLexer, stripped_queries)
        parsers = map(QueryParser, lexers)
        filters: Iterable[ast.FilterNode] = itertools.chain.from_iterable(
            map(QueryParser.parse, parsers)
        )
        filters = prepare_filters(filters, ast.Field.SECURITY)

        options = QueryOptions(filters=filters, limit=limit)
        res = self._repos.security.search_securities(options, ResultFormat.LIST)
        if not res:
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)
        elif len(res) == 1:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=SecurityRead(*res[0]),
                queries=queries,
            )
        else:
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=[SecurityRead(*row) for row in res],
                queries=queries,
            )
            # If we reach here, it means we have ambiguous results

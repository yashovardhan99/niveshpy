"""Security service for managing securities."""

from collections.abc import Sequence

from sqlmodel import select

from niveshpy.core import logging
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_filters_from_queries_v2
from niveshpy.database import get_session
from niveshpy.models.security import (
    Security,
    SecurityCategory,
    SecurityCreate,
    SecurityType,
)
from niveshpy.services.result import (
    InsertResult,
    MergeAction,
    ResolutionStatus,
    SearchResolution,
)


class SecurityService:
    """Service handler for the securities command group."""

    _column_mappings: dict[ast.Field, list[str]] = {
        ast.Field.SECURITY: ["key", "name"],
        ast.Field.TYPE: ["type", "category"],
    }

    def list_securities(
        self,
        queries: tuple[str, ...],
        limit: int = 30,
        offset: int = 0,
    ) -> Sequence[Security]:
        """List securities matching the query."""
        where_clause = get_filters_from_queries_v2(
            queries, ast.Field.SECURITY, self._column_mappings
        )
        with get_session() as session:
            return session.exec(
                select(Security).where(*where_clause).offset(offset).limit(limit)
            ).all()

    def add_security(
        self,
        key: str,
        name: str,
        stype: SecurityType,
        category: SecurityCategory,
        source: str | None = None,
    ) -> InsertResult[Security]:
        """Add a single security to the database."""
        if not key.strip() or not name.strip():
            raise ValueError("Security key and name cannot be empty.")
        if stype not in SecurityType:
            raise ValueError(f"Invalid security type: {stype}")
        if category not in SecurityCategory:
            raise ValueError(f"Invalid security category: {category}")

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

        with get_session() as session:
            # Check existing
            existing = session.get(Security, security.key)

            if existing is not None:
                logging.logger.debug("Updating existing security: %s", existing)

                # Update existing security
                existing.name = security.name
                existing.type = security.type
                existing.category = security.category
                existing.properties = security.properties
                db_security = existing
            else:
                db_security = Security.model_validate(security)

            # Insert or update security
            session.add(db_security)
            session.commit()

            session.refresh(db_security)

            if existing is not None:
                return InsertResult(MergeAction.UPDATE, db_security)
            else:
                return InsertResult(MergeAction.INSERT, db_security)

    def delete_security(self, key: str) -> bool:
        """Delete a security by its key.

        Returns True if a security was deleted, False otherwise.
        """
        with get_session() as session:
            security = session.get(Security, key)
            if security is None:
                return False
            session.delete(security)
            session.commit()
            return True

    def resolve_security_key(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> SearchResolution[Security]:
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

            securities = self.list_securities(queries, limit=limit)
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=securities,
                queries=queries,
            )

        # First, try to find an exact match by key
        with get_session() as session:
            exact_security = session.get(Security, queries[0].strip())
        if exact_security is not None:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=exact_security,
                queries=queries,
            )

        if not allow_ambiguous:
            # If ambiguous results are not allowed, return NOT_FOUND
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)

        # Perform a text search for candidates
        securities = self.list_securities(queries, limit=limit)
        if not securities:
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)
        elif len(securities) == 1:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=securities[0],
                queries=queries,
            )
        else:
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=securities,
                queries=queries,
            )
            # If we reach here, it means we have ambiguous results

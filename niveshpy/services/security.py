"""Security service for managing securities."""

from collections.abc import Sequence

from sqlmodel import select

from niveshpy.core import logging
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_filters_from_queries
from niveshpy.database import get_session
from niveshpy.exceptions import AmbiguousResourceError, InvalidInputError
from niveshpy.models.security import (
    SECURITY_COLUMN_MAPPING,
    Security,
    SecurityCategory,
    SecurityCreate,
    SecurityType,
)
from niveshpy.services.result import (
    InsertResult,
    MergeAction,
)


class SecurityService:
    """Service handler for the securities command group."""

    def list_securities(
        self,
        queries: tuple[str, ...],
        limit: int = 30,
        offset: int = 0,
    ) -> Sequence[Security]:
        """List securities matching the query."""
        if limit < 1:
            raise InvalidInputError(limit, "Limit must be positive.")
        if offset < 0:
            raise InvalidInputError(offset, "Offset cannot be negative.")

        where_clause = get_filters_from_queries(
            queries, ast.Field.SECURITY, SECURITY_COLUMN_MAPPING
        )
        with get_session() as session:
            return session.exec(
                select(Security)
                .where(*where_clause)
                .offset(offset)
                .limit(limit)
                .order_by(Security.key)
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

        with get_session() as session:
            # Check existing
            existing = session.get(Security, security.key)

            if existing is not None:
                logging.logger.debug("Updating existing security: %s", existing)

                # Update existing security
                existing.name = security.name
                existing.type = security.type
                existing.category = security.category
                if source:
                    props = existing.properties.copy()
                    props.update(security.properties)
                    existing.properties = props
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
            with get_session() as session:
                exact_security = session.get(Security, security_key)
                if exact_security is not None:
                    return [exact_security]

        # No exact match found by key
        # If ambiguous results are not allowed, raise error
        if not allow_ambiguous:
            raise AmbiguousResourceError("security", " ".join(queries))

        # Perform a text search for candidates
        return self.list_securities(queries, limit=limit)

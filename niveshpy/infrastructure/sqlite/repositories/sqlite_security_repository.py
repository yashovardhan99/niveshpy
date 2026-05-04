"""Repository module for performing database operations related to security entities."""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import chain
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.exceptions import ResourceNotFoundError
from niveshpy.infrastructure.sqlite.models import Security
from niveshpy.infrastructure.sqlite.query_filters import get_sqlalchemy_filters
from niveshpy.models.security import SecurityCreate, SecurityPublic


@dataclass(slots=True, frozen=True)
class SqliteSecurityRepository:
    """Repository for performing database operations related to securities.

    Attributes:
        session_factory: The sessionmaker instance used for creating database sessions.
    """

    session_factory: sessionmaker[Session]

    # SELECT operations for single security

    def get_security_by_key(self, key: str) -> SecurityPublic | None:
        """Fetch a security by its unique key."""
        with self.session_factory() as session:
            security = session.get(Security, key)
            logger.debug("Fetched security by key '%s': %s", key, str(security))
            return security.to_public() if security else None

    # SELECT operations for multiple securities

    def find_securities(
        self, filters: list[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[SecurityPublic]:
        """Find securities matching the given filters with optional pagination."""
        where_clause = get_sqlalchemy_filters(
            filters,
            {
                Field.SECURITY: ["key", "name"],
                Field.TYPE: ["type", "category"],
            },
        )
        with self.session_factory() as session:
            securities = session.scalars(
                select(Security)
                .where(*where_clause)
                .offset(offset)
                .limit(limit)
                .order_by(Security.key)
            ).all()
            logger.debug(
                "Fetched securities with filters %s, limit %s, offset %s: %d results",
                filters,
                limit,
                offset,
                len(securities),
            )
            return [sec.to_public() for sec in securities]

    def find_securities_by_keys(self, keys: Sequence[str]) -> Sequence[SecurityPublic]:
        """Find securities matching the given list of keys."""
        if not keys:
            return []
        with self.session_factory() as session:
            securities = session.scalars(
                select(Security).where(Security.key.in_(keys))
            ).all()
            logger.debug(
                "Fetched securities by %d keys: %d results", len(keys), len(securities)
            )
            return [sec.to_public() for sec in securities]

    # INSERT operations for single security

    def insert_security(self, security: SecurityCreate) -> bool:
        """Insert a new security into the database."""
        with self.session_factory() as session:
            stmt = (
                sqlite_insert(Security)
                .values(
                    key=security.key,
                    name=security.name,
                    type=security.type,
                    category=security.category,
                    properties=security.properties,
                )
                .on_conflict_do_nothing()
            )
            result = cast(CursorResult, session.execute(stmt)).rowcount
            session.commit()
            if result == 0:
                logger.debug("Security already exists, skipping insert: %s", security)
                return False
            logger.debug("Inserted new security with key: %s", security.key)
            return True

    # INSERT operations for multiple securities

    def insert_multiple_securities(self, securities: Sequence[SecurityCreate]) -> int:
        """Insert multiple securities into the database."""
        security_dicts = [
            {
                "key": sec.key,
                "name": sec.name,
                "type": sec.type,
                "category": sec.category,
                "properties": sec.properties,
            }
            for sec in securities
        ]
        if not security_dicts:
            logger.debug("No securities provided for bulk insert.")
            return 0

        with self.session_factory() as session:
            stmt = (
                sqlite_insert(Security).values(security_dicts).on_conflict_do_nothing()
            )
            result = cast(CursorResult, session.execute(stmt)).rowcount

            session.commit()
            logger.debug(
                "Inserted %d new securities out of %d provided.",
                result,
                len(securities),
            )
            return result

    # DELETE operations

    def delete_security_by_key(self, key: str) -> bool:
        """Delete a security from the database by its key."""
        stmt = delete(Security).where(Security.key == key)
        with self.session_factory() as session:
            result = cast(CursorResult, session.execute(stmt)).rowcount
            if result == 0:
                logger.debug("No security found with key %s to delete.", key)
                return False
            session.commit()
            logger.debug("Deleted security with key %s.", key)
            return True

    # UPDATE operations

    def update_security_properties(
        self,
        security_key: str,
        *properties: tuple[str, Any],
    ) -> None:
        """Update specific properties of an existing security.

        Only the provided properties are updated. Existing properties not
        included in `properties` are preserved.

        Args:
            security_key: The unique key of the security to update.
            *properties: Variable-length `(name, value)` pairs representing
                the properties to update in the security's JSON properties
                field.

        Raises:
            ResourceNotFoundError: If no security exists with the given key.
        """
        if not properties:
            return  # Nothing to update

        # JSON_SET requires keys in the format of "$.propertyName" to update
        # specific properties within the JSON column
        # and flatten the list for JSON_SET arguments
        args = chain.from_iterable((f"$.{name}", value) for name, value in properties)

        stmt = (
            update(Security)
            .where(Security.key == security_key)
            .values(properties=func.json_set(Security.properties, *args))
        )
        with self.session_factory() as session:
            result = cast(CursorResult, session.execute(stmt)).rowcount
            if result == 0:
                raise ResourceNotFoundError("Security", security_key)
            session.commit()
            logger.debug(
                "Updated properties %s for security with key %s.",
                [name for name, _ in properties],
                security_key,
            )

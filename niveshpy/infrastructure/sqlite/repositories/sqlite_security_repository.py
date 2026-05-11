"""Repository module for performing database operations related to security entities."""

from collections.abc import Sequence
from itertools import chain
from textwrap import dedent
from typing import Any

from attrs import frozen

from niveshpy.core.logging import logger
from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.exceptions import ResourceNotFoundError
from niveshpy.infrastructure.sqlite.converters import get_converter
from niveshpy.infrastructure.sqlite.query import (
    SECURITY_COLUMNS,
    Col,
    Delete,
    Insert,
    Query,
    in_,
)
from niveshpy.infrastructure.sqlite.query_filters import generate_query_from_filters
from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase
from niveshpy.models.security import SecurityCreate, SecurityPublic


@frozen
class SqliteSecurityRepository:
    """Repository for performing database operations related to securities.

    Attributes:
        database: The SqliteDatabase instance used for executing queries.
        security_table_name: The name of the securities table in the database.
    """

    database: SqliteDatabase
    security_table_name: str = "security"

    # SELECT operations for single security

    def get_security_by_key(self, key: str) -> SecurityPublic | None:
        """Fetch a security by its unique key."""
        query = (
            Query()
            .select(*SECURITY_COLUMNS)
            .from_(self.security_table_name)
            .where(Col("key").eq(key))
        )
        return self.database.select_one(query, cl=SecurityPublic)

    # SELECT operations for multiple securities

    def find_securities(
        self, filters: list[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[SecurityPublic]:
        """Find securities matching the given filters with optional pagination."""
        query = (
            generate_query_from_filters(
                filters,
                {
                    Field.SECURITY: [Col("key"), Col("name")],
                    Field.TYPE: [Col("type"), Col("category")],
                },
            )
            .from_(self.security_table_name)
            .select(*SECURITY_COLUMNS)
            .order_by("key")
        )
        if limit is not None:
            query = query.limit(limit)
        if offset > 0:
            query = query.offset(offset)
        return self.database.select_many(query, cl=SecurityPublic)

    def find_securities_by_keys(self, keys: Sequence[str]) -> Sequence[SecurityPublic]:
        """Find securities matching the given list of keys."""
        if not keys:
            return []

        query = (
            Query()
            .select(*SECURITY_COLUMNS)
            .from_(self.security_table_name)
            .where(in_("key", *keys))
        )
        return self.database.select_many(query, cl=SecurityPublic)

    # INSERT operations for single security

    def insert_security(self, security: SecurityCreate) -> bool:
        """Insert a new security into the database."""
        c = get_converter()
        stmt = (
            Insert(self.security_table_name)
            .or_ignore()
            .columns("key", "name", "type", "category", "properties")
        ).values_(*c.unstructure_attrs_astuple(security))
        result = self.database.execute(stmt)
        if result == 0:
            logger.debug("Security already exists, skipping insert: %s", security)
            return False
        else:
            logger.debug("Inserted new security with key: %s", security.key)
            return True

    # INSERT operations for multiple securities

    def insert_multiple_securities(self, securities: Sequence[SecurityCreate]) -> int:
        """Insert multiple securities into the database."""
        if not securities:
            logger.debug("No securities provided for bulk insert.")
            return 0

        stmt = (
            Insert(self.security_table_name)
            .or_ignore()
            .columns("key", "name", "type", "category", "properties")
        )
        c = get_converter()
        security_tuples = [c.unstructure_attrs_astuple(sec) for sec in securities]

        result = self.database.executemany(stmt, security_tuples)
        logger.debug(
            "Inserted %d new securities out of %d provided.",
            result,
            len(securities),
        )
        return result

    # DELETE operations

    def delete_security_by_key(self, key: str) -> bool:
        """Delete a security from the database by its key."""
        stmt = Delete(self.security_table_name).where(Col("key").eq(key))
        result = self.database.execute(stmt)
        if result == 0:
            logger.debug("No security found with key %s to delete.", key)
            return False
        else:
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
        args = tuple(
            chain.from_iterable((f"$.{name}", value) for name, value in properties)
        ) + (security_key,)

        placeholders = ", ".join(["?"] * (len(properties) * 2))

        # An update query builder is not available yet
        # as this is the only update operation needed so far,
        # and it has a specific structure due to JSON_SET usage.
        stmt = dedent(
            f"""UPDATE {self.security_table_name}
            SET properties = json_set(properties, {placeholders})
            WHERE key = ?"""  # noqa: S608 - table name is not user input, and parameters are used for all values
        )

        with self.database.cursor() as cursor:
            result = cursor.execute(stmt, args)
            if result.rowcount == 0:
                raise ResourceNotFoundError("Security", security_key)
            logger.debug(
                "Updated properties %s for security with key %s.",
                [name for name, _ in properties],
                security_key,
            )

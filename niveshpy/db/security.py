"""Security Repository."""

from dataclasses import asdict
from typing import Literal, overload

import polars as pl

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.db.database import Database
from niveshpy.db.query import (
    DEFAULT_QUERY_OPTIONS,
    QueryOptions,
    ResultFormat,
    prepare_query_filters,
)
from niveshpy.models.security import SecurityRead, SecurityWrite


class SecurityRepository:
    """Repository for managing securities in the database."""

    _table_name = "securities"
    _column_mappings = {
        ast.Field.SECURITY: ["key", "name"],
        ast.Field.TYPE: ["type", "category"],
    }

    def __init__(self, db: Database):
        """Initialize the SecurityRepository."""
        self._db = db

    def count_securities(self, options: QueryOptions = DEFAULT_QUERY_OPTIONS) -> int:
        """Count the number of securities matching the query options."""
        query = f"SELECT COUNT(*) FROM {self._table_name}"
        if options.filters:
            filter_query, params = prepare_query_filters(
                options.filters, self._column_mappings
            )
            query += " WHERE " + filter_query
        else:
            params = ()
        query += ";"

        logger.debug("Executing count query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            res = cursor.execute(query, params)
            count = res.fetchone()
            return count[0] if count is not None else 0

    @overload
    def search_securities(
        self, options: QueryOptions, format: Literal[ResultFormat.POLARS]
    ) -> pl.DataFrame: ...

    @overload
    def search_securities(
        self, options: QueryOptions, format: Literal[ResultFormat.SINGLE]
    ) -> tuple | None: ...

    @overload
    def search_securities(
        self, options: QueryOptions, format: Literal[ResultFormat.LIST]
    ) -> list[tuple]: ...

    def search_securities(
        self,
        options: QueryOptions = DEFAULT_QUERY_OPTIONS,
        format: ResultFormat = ResultFormat.POLARS,
    ) -> pl.DataFrame | tuple | None | list[tuple]:
        """Search for securities matching the query options."""
        query = f"SELECT * FROM {self._table_name}"
        if options.filters:
            filter_query, _params = prepare_query_filters(
                options.filters, self._column_mappings
            )
            query += " WHERE " + filter_query
            params = list(_params)
        else:
            params = []

        query += " ORDER BY key"

        if options.limit is not None:
            query += " LIMIT ?"
            params.append(str(options.limit))

        if options.offset is not None:
            query += " OFFSET ?"
            params.append(str(options.offset))
        query += ";"

        logger.debug("Executing query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            res = cursor.execute(query, params)
            if format == ResultFormat.POLARS:
                return res.pl()
            elif format == ResultFormat.SINGLE:
                return res.fetchone()
            else:
                return res.fetchall()

    def get_security(self, key: str) -> SecurityRead | None:
        """Get a security by its key."""
        with self._db.cursor() as cursor:
            res = cursor.execute(
                f"SELECT * FROM {self._table_name} WHERE key = ?;",
                (key,),
            ).fetchone()
            return SecurityRead(*res) if res else None

    def insert_single_security(
        self, security: SecurityWrite
    ) -> tuple[str, SecurityRead] | None:
        """Add a single security to the database.

        If a security with the same key exists, it will be updated.
        Returns 'INSERT' if a new security was added, 'UPDATE' if an existing security
        was updated.
        """
        with self._db.cursor() as cursor:
            res = cursor.execute(
                f"""INSERT OR REPLACE INTO {self._table_name}
                (key, name, type, category, metadata)
                VALUES (?, ?, ?, ?, ?)
                RETURNING merge_action, *;
                """,
                (
                    security.key,
                    security.name,
                    security.type,
                    security.category,
                    security.metadata,
                ),
            ).fetchone()
            cursor.commit()
            return (res[0], SecurityRead(*res[1:])) if res else None

    def insert_multiple_securities(
        self, securities: list[SecurityWrite]
    ) -> list[SecurityRead]:
        """Add new securities to the database."""
        with self._db.cursor() as cursor:
            cursor.begin()
            cursor.register(
                "new_securities",
                pl.from_dicts(
                    map(asdict, securities),
                ),
            )
            cursor.execute(
                f"""MERGE INTO {self._table_name} target
                USING (SELECT * FROM new_securities) AS new
                ON target.key = new.key
                WHEN MATCHED THEN UPDATE BY NAME
                WHEN NOT MATCHED THEN INSERT BY NAME

                RETURNING *;
                """
            )
            res = cursor.fetchall()
            cursor.commit()

        return [SecurityRead(*data) for data in res]

    def delete_security(self, key: str) -> SecurityRead | None:
        """Delete a security by its key.

        Returns the deleted security if successful, None otherwise.
        """
        with self._db.cursor() as cursor:
            res = cursor.execute(
                f"DELETE FROM {self._table_name} WHERE key = ? RETURNING *;",
                (key,),
            )
            cursor.commit()
            data = res.fetchone()
            return SecurityRead(*data) if data else None

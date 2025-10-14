"""Security Repository."""

from collections.abc import Iterable
from dataclasses import asdict
from typing import Literal, overload

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.db.database import Database
from niveshpy.db.query import (
    DEFAULT_QUERY_OPTIONS,
    QueryOptions,
    ResultFormat,
    prepare_query_filters,
)
import polars as pl
from niveshpy.models.security import Security


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

    def get_security(self, key: str) -> Security | None:
        """Get a security by its key."""
        with self._db.cursor() as cursor:
            res = cursor.execute(
                f"SELECT * FROM {self._table_name} WHERE key = ?;",
                (key,),
            ).fetchone()
            return Security(*res) if res else None

    def insert_single_security(self, security: Security) -> str | None:
        """Add a single security to the database.

        If a security with the same key exists, it will be updated.
        Returns 'INSERT' if a new security was added, 'UPDATE' if an existing security
        was updated.
        """
        with self._db.cursor() as cursor:
            res = cursor.execute(
                f"""INSERT OR REPLACE INTO {self._table_name} 
                (key, name, type, category)
                VALUES (?, ?, ?, ?)
                RETURNING merge_action;
                """,
                (security.key, security.name, security.type, security.category),
            ).fetchone()
            cursor.commit()
            return res[0] if res is not None else None

    def merge_securities(
        self, securities: Iterable[Security] | pl.DataFrame
    ) -> pl.DataFrame:
        """Add new securities to the database."""
        if isinstance(securities, pl.DataFrame):
            df = securities
        else:
            df = pl.from_dicts(map(asdict, securities))

        with self._db.cursor() as cursor:
            cursor.register("new_securities", df)
            cursor.execute(
                f"""MERGE INTO {self._table_name} target
                USING (SELECT * FROM new_securities) AS new
                ON target.key = new.key
                WHEN MATCHED THEN UPDATE
                WHEN NOT MATCHED THEN INSERT BY NAME
                
                RETURNING merge_action, *;
                """
            )
            cursor.commit()
            return cursor.pl()

    def delete_security(self, key: str) -> Security | None:
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
            return Security(*data) if data else None

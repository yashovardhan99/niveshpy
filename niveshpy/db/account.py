"""Account database operations."""

from typing import Literal, overload

import polars as pl

from niveshpy.core.query import ast
from niveshpy.db.database import Database
from niveshpy.db.query import (
    DEFAULT_QUERY_OPTIONS,
    QueryOptions,
    ResultFormat,
    prepare_query_filters,
)
from niveshpy.models.account import AccountRead


class AccountRepository:
    """Repository for managing investment accounts in the database."""

    _table_name = "accounts"
    _column_mappings = {
        ast.Field.ACCOUNT: ["name", "institution"],
    }

    def __init__(self, db: Database):
        """Initialize the AccountRepository."""
        self._db = db

    @overload
    def search_accounts(
        self, options: QueryOptions, format: Literal[ResultFormat.POLARS]
    ) -> pl.DataFrame: ...

    @overload
    def search_accounts(
        self, options: QueryOptions, format: Literal[ResultFormat.SINGLE]
    ) -> tuple | None: ...

    @overload
    def search_accounts(
        self, options: QueryOptions, format: Literal[ResultFormat.LIST]
    ) -> list[tuple]: ...

    def search_accounts(
        self,
        options: QueryOptions = DEFAULT_QUERY_OPTIONS,
        format: ResultFormat = ResultFormat.POLARS,
    ) -> pl.DataFrame | tuple | None | list[tuple]:
        """Search for accounts matching the query options."""
        query = f"SELECT * FROM {self._table_name}"
        if options.filters:
            filter_query, _params = prepare_query_filters(
                options.filters, self._column_mappings
            )
            query += " WHERE " + filter_query
            params = list(_params)
        else:
            params = []

        query += " ORDER BY id"
        if options.limit:
            query += " LIMIT ?"
            params.append(str(options.limit))
        if options.offset:
            query += " OFFSET ?"
            params.append(str(options.offset))
        query += ";"

        with self._db.cursor() as cursor:
            res = cursor.execute(query, params)
            if format == ResultFormat.POLARS:
                return res.pl()
            elif format == ResultFormat.SINGLE:
                return res.fetchone()
            else:
                return res.fetchall()

    def get_account(self, id: int) -> AccountRead | None:
        """Retrieve an account by its ID."""
        query = f"SELECT id, name, institution, created_at, metadata FROM {self._table_name} WHERE id = ?;"
        params = (id,)

        with self._db.cursor() as cursor:
            res = cursor.execute(query, params).fetchone()
            return AccountRead(*res) if res else None

"""Module for handling database query results."""

from typing import Literal, overload, TypeVar
from duckdb import DuckDBPyConnection

import polars as pl

T = TypeVar("T")


class Result:
    """Class representing the result of a database select operation."""

    def __init__(self, connection: DuckDBPyConnection):
        """Initialize the Result with a DuckDB connection."""
        self._conn = connection

    @overload
    def get(self, n: Literal[1], cls: Literal[None]) -> tuple: ...  # type: ignore[misc]

    @overload
    def get(self, n: Literal[1], cls: type[T]) -> T: ...  # type: ignore[misc]

    @overload
    def get(self, n: int, cls: Literal[None]) -> list[tuple]: ...

    @overload
    def get(self, n: int, cls: type[T]) -> list[T]: ...

    def get(
        self, n: int = 1, cls: type[T] | None = None
    ) -> T | list[T] | tuple | list[tuple]:
        """Fetch n results from the last executed query."""
        if n == 1:
            row = self._conn.fetchone()
            if cls is None:
                return row
            return cls(*row)

        rows = self._conn.fetchmany(n)
        if cls is None:
            return rows
        return [cls(*row) for row in rows]

    @overload
    def pl(self, *args, lazy: Literal[False] = False, **kwargs) -> "pl.DataFrame": ...

    @overload
    def pl(self, *args, lazy: Literal[True], **kwargs) -> "pl.LazyFrame": ...

    def pl(self, *args, lazy: bool = False, **kwargs) -> "pl.DataFrame | pl.LazyFrame":
        """Fetch all results as a Polars DataFrame."""
        return self._conn.pl(*args, lazy=lazy, **kwargs)

    def __iter__(self):
        """Return an iterator over all results."""
        return self

    def __next__(self):
        """Fetch the next result."""
        row = self.get()
        if row is None:
            raise StopIteration
        return row

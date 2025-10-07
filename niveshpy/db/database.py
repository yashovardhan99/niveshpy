"""Database configuration and connection management."""

from __future__ import annotations

from pathlib import Path

import duckdb
import platformdirs

# Resolve application data directory and database file
app_path = platformdirs.user_data_path("niveshpy")
app_path.mkdir(parents=True, exist_ok=True)
_db_path = (app_path / "niveshpy.db").resolve()


class Database:
    """Manages a DuckDB connection lifecycle."""

    _conn: duckdb.DuckDBPyConnection | None

    def __init__(
        self,
        path: Path | None = _db_path,
    ):
        """Initialize the Database instance."""
        self._path = path.as_posix() if path else ":memory:"
        self._conn = None

    def cursor(self) -> duckdb.DuckDBPyConnection:
        """Get a cursor, opening the connection if necessary."""
        if self._conn is None:
            self._conn = duckdb.connect(database=self._path)
        return self._conn.cursor()

    def close(self) -> None:
        """Close the database connection if open."""
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    # Context manager support
    def __enter__(self) -> Database:
        """Enter context, ensuring connection is open."""
        self.cursor().close()  # Ensure connection is established
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Exit context, closing the connection."""
        self.close()

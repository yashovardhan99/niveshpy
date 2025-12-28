"""Database configuration and connection management."""

from __future__ import annotations

from pathlib import Path

import duckdb
import platformdirs

from niveshpy.core import logging

# Resolve application data directory and database file
app_path = platformdirs.user_data_path("niveshpy")
app_path.mkdir(parents=True, exist_ok=True)
_db_path = (app_path / "niveshpy.db").resolve()


class DatabaseError(Exception):
    """Exception for database-related errors."""


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

    def _initialize_tables(self) -> None:
        """Initialize required tables in the database."""
        sql_file_path = Path(__file__).parent / "init.sql"
        with open(sql_file_path) as file:
            sql_script = file.read()
        with self.cursor() as cursor:
            cursor.begin()
            cursor.execute(sql_script)
            cursor.commit()
        logging.logger.info("Initialized database tables.")

    def _initialize(self) -> duckdb.DuckDBPyConnection:
        """Initialize the database connection."""
        if self._conn is None:
            try:
                self._conn = duckdb.connect(database=self._path)
                logging.logger.info("Connected to database at path: %s", self._path)
                self._initialize_tables()
            except duckdb.ConnectionException as e:
                raise DatabaseError("Failed to connect to the database.") from e
            except duckdb.IOException as e:
                raise DatabaseError(
                    "I/O error occurred while accessing the database."
                ) from e
        return self._conn

    def cursor(self) -> duckdb.DuckDBPyConnection:
        """Get a cursor, opening the connection if necessary."""
        return self._initialize().cursor()

    def close(self) -> None:
        """Close the database connection if open."""
        if self._conn is not None:
            logging.logger.info("Closing database connection.")
            try:
                self._conn.close()
                logging.logger.debug("Database connection closed.")
            finally:
                self._conn = None

    # Context manager support
    def __enter__(self) -> Database:
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Exit context, closing the connection."""
        self.close()

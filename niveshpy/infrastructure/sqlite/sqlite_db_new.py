"""Sqlite database session management and migrations."""

import atexit
import functools
import re
import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent
from typing import TypeVar, overload

import platformdirs
from attrs import field, frozen
from cattrs import Converter

from niveshpy.core.logging import logger
from niveshpy.exceptions import DatabaseError, IntegrityError
from niveshpy.infrastructure.sqlite.converters import get_converter
from niveshpy.infrastructure.sqlite.query import Delete, Insert, Query


def _iregexp(pattern: str, value: str | None) -> bool:
    """Case-insensitive regex match for SQLite."""
    if value is None:
        return False
    return bool(re.search(pattern, value, re.IGNORECASE))


T = TypeVar("T")


@frozen
class SqliteDatabase:
    """SQLite database session management and migrations."""

    db_path: Path = field(
        factory=lambda: platformdirs.user_data_path("niveshpy") / "niveshpy.db"
    )
    _converter: Converter = field(init=False, repr=False, factory=get_converter)

    @functools.cached_property
    def connection(self) -> sqlite3.Connection:
        """Get a new SQLite database connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            logger.debug("SQLite connection established to %s", self.db_path)
            conn.set_trace_callback(logger.debug)
            conn.create_function("iregexp", 2, _iregexp)
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            atexit.register(conn.close)
            return conn
        except sqlite3.Error as e:
            raise DatabaseError("Error connecting to the SQLite database") from e

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Get a new database cursor."""
        with self.connection as conn:
            try:
                cursor = conn.cursor()
                yield cursor
            except sqlite3.IntegrityError as e:
                raise IntegrityError(*e.args) from e
            except sqlite3.Error as e:
                raise DatabaseError(*e.args) from e
            finally:
                cursor.close()

    def initialize(self) -> None:
        """Initialize the database and run migrations."""
        logger.info("Initializing database at path: %s", self.db_path)
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run database migrations to ensure the schema is up to date."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Create a simple migrations table if it doesn't exist
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    dedent("""\
                    CREATE TABLE IF NOT EXISTS migration (
                        id INTEGER PRIMARY KEY,
                        file VARCHAR NOT NULL UNIQUE,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                )
        except sqlite3.Error as e:
            raise DatabaseError("Failed to create migration table") from e

        # Check for pending migration files and apply them
        migrations_folder = Path(__file__).parent / "migrations"
        try:
            with self.cursor() as cursor:
                cursor.execute("SELECT file FROM migration")
                applied_migrations = {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            raise DatabaseError("Failed to read applied migrations") from e

        # Sort migration files to ensure they are applied in the correct order
        migration_files = sorted(migrations_folder.glob("*.sql"))
        for migration_file in migration_files:
            if migration_file.name not in applied_migrations:
                logger.info("Applying migration: %s", migration_file.stem)
                migration_sql_contents = migration_file.read_text()
                try:
                    with self.cursor() as cursor:
                        cursor.executescript(migration_sql_contents)
                        cursor.execute(
                            "INSERT INTO migration (file) VALUES (?)",
                            (migration_file.name,),
                        )
                except sqlite3.Error as e:
                    raise DatabaseError(
                        f"Failed to apply migration: {migration_file.name}"
                    ) from e

    @overload
    def select_many(self, query: Query, cl: type[T] = ...) -> Sequence[T]: ...

    @overload
    def select_many(self, query: Query, cl: None = ...) -> Sequence[sqlite3.Row]: ...

    def select_many(
        self, query: Query, cl: type[T] | None = None
    ) -> Sequence[sqlite3.Row] | Sequence[T]:
        """Execute a SELECT query and return the results as a list of rows or structured objects.

        Args:
            query: The SQL query to execute.
            cl: Optional class type to structure the results into. If None, returns sqlite3.Row objects.

        Returns:
            A sequence of results, either as sqlite3.Row objects or structured instances of the specified class.

        Raises:
            DatabaseError: If there is an error executing the query.
        """
        try:
            with self.connection as conn:
                query_str = str(query)
                query_params = query.params
                results = conn.execute(query_str, query_params).fetchall()
                logger.debug("Query returned %d rows", len(results))

            if cl is not None:
                # If a class is provided, structure the results into instances of that class
                return [
                    self._converter.structure(dict(result), cl) for result in results
                ]
            else:
                # Otherwise, return the raw sqlite3.Row objects
                return results
        except sqlite3.Error as e:
            raise DatabaseError("Failed to execute SELECT query") from e

    @overload
    def select_one(self, query: Query, cl: type[T] = ...) -> T | None: ...

    @overload
    def select_one(self, query: Query, cl: None = ...) -> sqlite3.Row | None: ...

    def select_one(
        self, query: Query, cl: type[T] | None = None
    ) -> T | sqlite3.Row | None:
        """Execute a SELECT query and return a single result as a row or structured object.

        Args:
            query: The SQL query to execute.
            cl: Optional class type to structure the result into. If None, returns a sqlite3.Row object.

        Returns:
            A single result, either as a sqlite3.Row object or a structured instance of the specified class, or None if no results are found.

        Raises:
            DatabaseError: If there is an error executing the query.
        """
        try:
            with self.connection as conn:
                query_str = str(query)
                query_params = query.params
                result = conn.execute(query_str, query_params).fetchone()
                logger.debug("Query returned 1 row: %s", str(result))

            if result is None:
                return None

            if cl is not None:
                # If a class is provided
                return self._converter.structure(dict(result), cl)
            else:
                # Otherwise, return the raw sqlite3.Row object
                return result
        except sqlite3.Error as e:
            raise DatabaseError("Failed to execute SELECT query") from e

    def execute(self, stmt: Insert | Delete) -> int:
        """Execute an INSERT or DELETE statement and return the number of affected rows.

        Args:
            stmt: The SQL statement to execute.

        Returns:
            The number of rows affected by the statement.

        Raises:
            DatabaseError: If there is an error executing the statement.
        """
        try:
            with self.connection as conn:
                stmt_str = str(stmt)
                stmt_params = stmt.params
                result = conn.execute(stmt_str, stmt_params)
                affected_rows = result.rowcount
                logger.debug("Statement affected %d rows", affected_rows)
                return affected_rows
        except sqlite3.IntegrityError as e:
            raise IntegrityError() from e
        except sqlite3.Error as e:
            raise DatabaseError("Failed to execute statement") from e

    def executemany(self, stmt: Insert | Delete, params_list: Sequence[tuple]) -> int:
        """Execute an INSERT or DELETE statement with multiple sets of parameters.

        Args:
            stmt: The SQL statement to execute.
            params_list: A sequence of parameter tuples to execute the statement with.

        Returns:
            The total number of rows affected by all executions of the statement.

        Raises:
            DatabaseError: If there is an error executing the statement.
        """
        try:
            with self.connection as conn:
                stmt_str = str(stmt)
                result = conn.executemany(stmt_str, params_list)
                affected_rows = result.rowcount
                logger.debug("Statement affected a total of %d rows", affected_rows)
                return affected_rows
        except sqlite3.IntegrityError as e:
            raise IntegrityError() from e
        except sqlite3.Error as e:
            raise DatabaseError("Failed to execute statement") from e

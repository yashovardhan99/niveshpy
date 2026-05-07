"""Sqlite database session management and migrations."""

import atexit
import functools
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent

import platformdirs
from attrs import field, frozen

from niveshpy.core.logging import logger
from niveshpy.exceptions import DatabaseError, IntegrityError


def _iregexp(pattern: str, value: str | None) -> bool:
    """Case-insensitive regex match for SQLite."""
    if value is None:
        return False
    return bool(re.search(pattern, value, re.IGNORECASE))


@frozen
class SqliteDatabase:
    """SQLite database session management and migrations."""

    db_path: Path = field(
        factory=lambda: platformdirs.user_data_path("niveshpy") / "niveshpy.db"
    )
    _debug: bool = field(default=False, repr=False, alias="debug")

    @functools.cached_property
    def connection(self) -> sqlite3.Connection:
        """Get a new SQLite database connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            logger.debug("SQLite connection established to %s", self.db_path)
            if self._debug:
                conn.set_trace_callback(logger.debug)
            conn.create_function("iregexp", 2, _iregexp)
            conn.execute("PRAGMA foreign_keys=ON")
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
        except DatabaseError as e:
            raise DatabaseError("Failed to create migration table") from e

        # Check for pending migration files and apply them
        migrations_folder = Path(__file__).parent / "migrations"
        try:
            with self.cursor() as cursor:
                cursor.execute("SELECT file FROM migration")
                applied_migrations = {row[0] for row in cursor.fetchall()}
        except DatabaseError as e:
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
                except DatabaseError as e:
                    raise DatabaseError(
                        f"Failed to apply migration: {migration_file.name}"
                    ) from e

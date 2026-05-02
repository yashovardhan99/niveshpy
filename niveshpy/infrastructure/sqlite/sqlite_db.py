"""SQLAlchemy class for database setup and connection management."""

import re
import sqlite3
from pathlib import Path

import platformdirs
from attrs import field, frozen
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from niveshpy.core.logging import logger


@frozen
class SqliteDatabase:
    """Manages database connection and migrations for the application.

    Attributes:
        debug (bool): Whether to enable debug logging for database operations.
        app_path (Path): Directory where the SQLite database file is stored.
        session (sessionmaker[Session]): SQLAlchemy session factory for database interactions.
    """

    _debug: bool = field(default=False, repr=False, alias="debug")
    app_path: Path = field(factory=lambda: platformdirs.user_data_path("niveshpy"))
    _db_path: Path = field(init=False)
    _sqlite_url: str = field(init=False)
    _engine: Engine = field(init=False)
    session_factory: sessionmaker[Session] = field(init=False)
    """SQLAlchemy session factory for database interactions.

    This attribute is initialized in the `initialize` method after the database engine is set up.
    It can be used to create new sessions for querying and modifying the database.
    """

    def __attrs_post_init__(self) -> None:
        """Initialize database paths, engine, and session factory."""
        self.app_path.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "_db_path", (self.app_path / "niveshpy.db").resolve())

        object.__setattr__(self, "_sqlite_url", f"sqlite:///{self._db_path}")

        object.__setattr__(
            self, "_engine", create_engine(self._sqlite_url, echo=self._debug)
        )

        # Enable foreign key constraints for SQLite
        @event.listens_for(self._engine, "connect")
        def set_sqlite_pragma(dbapi_conn: sqlite3.Connection, _):
            """Enable foreign key constraints and add custom functions for SQLite."""
            logger.debug("Setting SQLite PRAGMA and adding custom functions.")
            dbapi_conn.create_function("iregexp", 2, _iregexp)
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    def initialize(self, base: type[DeclarativeBase]) -> None:
        """Create database and tables if they do not exist."""
        logger.info("Initializing database at path: %s", self._db_path)
        object.__setattr__(self, "session_factory", sessionmaker(bind=self._engine))
        self.run_migrations()
        base.metadata.create_all(self._engine)

    def run_migrations(self) -> None:
        """Run database migrations to update schema as needed."""
        logger.debug("Running database migrations.")

        # Create Migration table if it doesn't exist
        stmt = """CREATE TABLE IF NOT EXISTS migration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file VARCHAR NOT NULL UNIQUE,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        with self.session_factory.begin() as session:
            session.execute(text(stmt))

        # Check for pending migration files and apply them
        migrations_folder = Path(__file__).parent / "migrations"
        applied_migrations = set()
        with self.session_factory() as session:
            result = session.execute(text("SELECT file FROM migration"))
            applied_migrations = {row[0] for row in result}

        # Sort migration files to ensure they are applied in the correct order
        migration_files = sorted(migrations_folder.glob("*.sql"))

        for migration_file in migration_files:
            if migration_file.name not in applied_migrations:
                logger.info("Applying migration: %s", migration_file.name)
                migration_sql_contents = migration_file.read_text()
                # Strip comments
                migration_sql_contents = re.sub(r"--.*", "", migration_sql_contents)
                # Split into individual statements
                statements = [
                    stmt.strip()
                    for stmt in re.split(r";\s*(?=\b)", migration_sql_contents)
                    if stmt.strip()
                ]
                with self.session_factory.begin() as session:
                    for statement in statements:
                        session.execute(text(statement))
                    session.execute(
                        text("INSERT INTO migration (file) VALUES (:file)"),
                        {"file": migration_file.name},
                    )


def _iregexp(pattern: str, value: str | None) -> bool:
    """Case-insensitive regex match for SQLite."""
    if value is None:
        return False
    return bool(re.search(pattern, value, re.IGNORECASE))

"""SqlModel class for database setup and connection management."""

import re
import sqlite3

import platformdirs
from sqlmodel import Session, SQLModel, create_engine

from niveshpy.core import logging

# Resolve application data directory and database file
app_path = platformdirs.user_data_path("niveshpy")
app_path.mkdir(parents=True, exist_ok=True)
_db_path = (app_path / "niveshpy.db").resolve()


_sqlite_url = f"sqlite:///{_db_path}"

_engine = create_engine(_sqlite_url, echo=False)


def _iregexp(pattern: str, value: str) -> bool:
    """Case-insensitive regex match for SQLite."""
    if value is None:
        return False
    return bool(re.search(pattern, value, re.IGNORECASE))


def initialize():
    """Create database and tables if they do not exist."""
    logging.logger.info("Creating database and tables at path: %s", _db_path)
    SQLModel.metadata.create_all(_engine)
    logging.logger.info("Database and tables created successfully.")

    logging.logger.info("Adding custom SQLite functions.")
    with _engine.connect() as conn:
        if isinstance(conn.connection.dbapi_connection, sqlite3.Connection):
            conn.connection.dbapi_connection.create_function("iregexp", 2, _iregexp)
    logging.logger.info("Custom SQLite functions added successfully.")


def get_session() -> Session:
    """Obtain a new database session."""
    return Session(_engine)

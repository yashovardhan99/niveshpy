"""SqlModel class for database setup and connection management."""

import re
import sqlite3

import platformdirs
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from niveshpy.core import logging

# Resolve application data directory and database file
app_path = platformdirs.user_data_path("niveshpy")
app_path.mkdir(parents=True, exist_ok=True)
_db_path = (app_path / "niveshpy.db").resolve()


_sqlite_url = f"sqlite:///{_db_path}"

_engine = create_engine(_sqlite_url, echo=False)


def _iregexp(pattern: str, value: str | None) -> bool:
    """Case-insensitive regex match for SQLite."""
    if value is None:
        return False
    return bool(re.search(pattern, value, re.IGNORECASE))


# Enable foreign key constraints for SQLite
@event.listens_for(_engine, "connect")
def set_sqlite_pragma(dbapi_conn: sqlite3.Connection, _):
    """Enable foreign key constraints and add custom functions for SQLite."""
    logging.logger.debug("Setting SQLite PRAGMA and adding custom functions.")
    dbapi_conn.create_function("iregexp", 2, _iregexp)
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def initialize():
    """Create database and tables if they do not exist."""
    logging.logger.info("Creating database and tables at path: %s", _db_path)
    SQLModel.metadata.create_all(_engine)


def get_session() -> Session:
    """Obtain a new database session."""
    return Session(_engine)

"""Pytest fixtures for database setup and teardown."""

import re

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine


def _iregexp(pattern: str, value: str) -> bool:
    """Case-insensitive regex match for SQLite."""
    if value is None:
        return False
    return bool(re.search(pattern, value, re.IGNORECASE))


@pytest.fixture
def engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine("sqlite:///:memory:")

    # Enable foreign key constraints and add custom functions for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        dbapi_conn.create_function("iregexp", 2, _iregexp)
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a new database session for a test."""
    with Session(engine) as session:
        yield session
        session.rollback()  # Clean up after each test

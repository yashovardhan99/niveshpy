"""Pytest fixtures for database setup and teardown."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture(scope="session", autouse=True)
def mock_platformdirs(tmp_path_factory):
    """Mock platformdirs to use temporary directory for tests.

    This prevents the database module from creating directories in the real
    user data path when imported during tests.
    """
    temp_dir = tmp_path_factory.mktemp("niveshpy_test_data")

    mock_path = MagicMock(spec=Path)
    mock_path.mkdir = MagicMock()
    mock_path.__truediv__ = lambda self, other: temp_dir / other
    mock_path.__str__ = lambda self: str(temp_dir)

    with patch("platformdirs.user_data_path", return_value=temp_dir):
        yield temp_dir


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

    from niveshpy.models.account import Account  # noqa: F401
    from niveshpy.models.price import Price  # noqa: F401
    from niveshpy.models.security import Security  # noqa: F401
    from niveshpy.models.transaction import Transaction  # noqa: F401

    # Import all models to ensure they are registered with SQLModel
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a new database session for a test."""
    with Session(engine) as session:
        yield session
        session.rollback()  # Clean up after each test

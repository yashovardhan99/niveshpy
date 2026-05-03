"""Pytest fixtures for database setup and teardown."""

from pathlib import Path
from unittest.mock import patch

import pytest

from niveshpy.infrastructure.sqlite.models import Base
from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase


@pytest.fixture(scope="session", autouse=True)
def mock_platformdirs(tmp_path_factory):
    """Mock platformdirs to use temporary directory for tests.

    This prevents the database module from creating directories in the real
    user data path when imported during tests.
    """
    temp_dir = tmp_path_factory.mktemp("niveshpy_test_data")

    with patch("platformdirs.user_data_path", return_value=temp_dir):
        yield temp_dir


@pytest.fixture
def db():
    """Create an in-memory SqliteDatabase for testing."""
    database = SqliteDatabase(db_path=Path(":memory:"))
    database.initialize(Base)
    return database


@pytest.fixture
def engine(db):
    """Expose the SQLAlchemy engine from the test database."""
    return db._engine


@pytest.fixture
def session(db):
    """Create a new database session for a test."""
    with db.session_factory() as session:
        yield session
        session.rollback()


@pytest.fixture
def session_factory(db):
    """Expose the session factory from the test database."""
    return db.session_factory

"""Pytest fixtures for database setup and teardown."""

import pytest
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a new database session for a test."""
    with Session(engine) as session:
        yield session
        session.rollback()  # Clean up after each test

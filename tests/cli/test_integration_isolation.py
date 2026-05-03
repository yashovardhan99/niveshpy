"""Safety checks for CLI integration test database isolation."""

from pathlib import Path

from niveshpy.core.app import Application
from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase
from tests.cli.conftest import CliScenario


def test_cli_integration_uses_in_memory_engine(cli_scenario: CliScenario) -> None:
    """CLI integration tests must run against an in-memory SQLite engine only."""
    app = Application()
    db = app.db

    assert isinstance(db, SqliteDatabase)
    assert db.db_path == Path(":memory:")
    assert str(db._engine.url) == "sqlite:///:memory:"

    # Sanity-check through a real CLI command while fixture patch is active.
    account_id = cli_scenario.add_account("Isolated", "TestBank")
    assert account_id == 1

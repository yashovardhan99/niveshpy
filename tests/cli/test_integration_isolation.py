"""Safety checks for CLI integration test database isolation."""

from sqlalchemy.pool import StaticPool

from tests.cli.conftest import CliScenario


def test_cli_integration_uses_in_memory_engine(cli_scenario: CliScenario) -> None:
    """CLI integration tests must run against an in-memory SQLite engine only."""
    import niveshpy.database as database

    assert str(database._engine.url) == "sqlite://"
    assert database._engine.url.database is None
    assert isinstance(database._engine.pool, StaticPool)

    # Sanity-check through a real CLI command while fixture patch is active.
    account_id = cli_scenario.add_account("Isolated", "TestBank")
    assert account_id == 1

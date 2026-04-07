"""Integration tests for security and price CLI flows."""

from tests.cli.conftest import CliScenario


def test_securities_add_list_filter_and_pagination(cli_scenario: CliScenario) -> None:
    """Securities can be added, filtered, and paginated through the CLI."""
    cli_scenario.add_security("AAA111", "Alpha Fund")
    cli_scenario.add_security("BBB222", "Beta Fund")
    cli_scenario.add_security("CCC333", "Gamma Fund")

    filtered = cli_scenario.invoke_json(["securities", "list", "Beta"])
    assert len(filtered) == 1
    assert filtered[0]["key"] == "BBB222"

    paged = cli_scenario.invoke_json(
        ["securities", "list", "--limit", "1", "--offset", "1"]
    )
    assert len(paged) == 1
    assert paged[0]["key"] == "BBB222"


def test_securities_add_existing_key_does_nothing(
    cli_scenario: CliScenario,
) -> None:
    """Adding a security with an existing key does nothing."""
    cli_scenario.add_security("INF123", "Old Name", "EQUITY", "MUTUAL_FUND")

    update_result = cli_scenario.invoke(
        [
            "securities",
            "add",
            "--no-input",
            "INF123",
            "New Name",
            "DEBT",
            "BOND",
        ]
    )

    assert "already exists" in update_result.output
    securities = cli_scenario.invoke_json(["securities", "list"])
    assert len(securities) == 1
    assert securities[0]["name"] == "Old Name"
    assert securities[0]["category"] == "equity"
    assert securities[0]["type"] == "mutual_fund"


def test_securities_delete_success_with_force(cli_scenario: CliScenario) -> None:
    """Securities can be deleted non-interactively by exact key."""
    cli_scenario.add_security("DEL123", "Delete Me")

    delete_result = cli_scenario.invoke(
        ["securities", "delete", "--no-input", "--force", "DEL123"]
    )

    assert "Security 'DEL123' was deleted successfully." in delete_result.output
    list_result = cli_scenario.invoke(["securities", "list"])
    assert "No securities found in the database." in list_result.output


def test_securities_delete_requires_force_in_no_input_mode(
    cli_scenario: CliScenario,
) -> None:
    """Securities delete must fail without --force in non-interactive mode."""
    cli_scenario.add_security("INF999", "Force Check")

    delete_without_force = cli_scenario.invoke(
        ["securities", "delete", "--no-input", "INF999"],
        expected_exit_code=1,
    )

    assert "--force must be provided" in delete_without_force.output


def test_prices_update_and_list_latest_price(cli_scenario: CliScenario) -> None:
    """Prices list returns the latest stored price per security by default."""
    cli_scenario.add_security("P001", "Priced Fund")
    cli_scenario.update_price("P001", "2025-01-10", "100.00")
    cli_scenario.update_price("P001", "2025-01-15", "110.00")

    prices = cli_scenario.invoke_json(["prices", "list"])
    assert len(prices) == 1
    assert prices[0]["security"]["key"] == "P001"
    assert prices[0]["date"] == "2025-01-15"
    assert prices[0]["close"] == "110.0000"


def test_prices_update_unknown_security_fails(cli_scenario: CliScenario) -> None:
    """Price updates fail with a not-found error for unknown securities."""
    result = cli_scenario.invoke(
        ["prices", "update", "UNKNOWN", "2025-01-15", "110.00"],
        expected_exit_code=1,
    )

    assert "Security with identifier 'UNKNOWN' not found." in result.output

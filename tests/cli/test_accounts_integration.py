"""Integration tests for account CLI flows."""

from click.testing import CliRunner

from niveshpy.cli.main import cli
from tests.cli.conftest import CliScenario


def test_accounts_add_list_filter_and_pagination(cli_scenario: CliScenario) -> None:
    """Accounts can be added, filtered, and paginated through the CLI."""
    cli_scenario.add_account("Alpha", "HDFC")
    cli_scenario.add_account("Beta", "ICICI")
    cli_scenario.add_account("Gamma", "SBI")

    filtered = cli_scenario.invoke_json(["accounts", "list", "Beta"])
    assert len(filtered) == 1
    assert filtered[0]["name"] == "Beta"

    paged = cli_scenario.invoke_json(
        ["accounts", "list", "--limit", "1", "--offset", "1"]
    )
    assert len(paged) == 1
    assert paged[0]["name"] == "Beta"


def test_accounts_add_duplicate_returns_warning_and_does_not_duplicate(
    cli_scenario: CliScenario,
) -> None:
    """Adding the same account twice warns and does not create a duplicate row."""
    account_id = cli_scenario.add_account("Primary", "HDFC")

    duplicate = cli_scenario.invoke(
        ["accounts", "add", "--no-input", "Primary", "HDFC"]
    )

    assert f"Account already exists with ID {account_id}." in duplicate.output
    accounts = cli_scenario.invoke_json(["accounts", "list"])
    assert len(accounts) == 1


def test_accounts_delete_success_by_id(cli_scenario: CliScenario) -> None:
    """Accounts can be deleted non-interactively by exact id."""
    account_id = cli_scenario.add_account("Disposable", "Axis")

    delete_result = cli_scenario.invoke(
        ["accounts", "delete", "--no-input", "--force", str(account_id)]
    )

    assert f"Account ID {account_id} was deleted successfully." in delete_result.output
    list_result = cli_scenario.invoke(["accounts", "list"])
    assert "No accounts found in the database." in list_result.output


def test_accounts_add_requires_name_and_institution_in_no_input_mode(
    runner: CliRunner,
) -> None:
    """Accounts add must fail in non-interactive mode when args are missing."""
    result = runner.invoke(cli, ["--no-color", "accounts", "add", "--no-input"])

    assert result.exit_code == 1
    assert "must be provided in non-interactive mode" in result.output

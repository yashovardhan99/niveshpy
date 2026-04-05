"""Integration tests for transaction CLI flows."""

from click.testing import CliRunner

from tests.cli.conftest import CliScenario


def test_transactions_add_list_and_delete_success(cli_scenario: CliScenario) -> None:
    """Transactions can be added, listed, and deleted through the CLI."""
    account_id = cli_scenario.add_account("Primary", "HDFC")
    cli_scenario.add_security("INF123", "Test Fund")

    transaction_id = cli_scenario.add_transaction(
        "2025-01-10",
        "purchase",
        "Initial buy",
        "1000.00",
        "10.000",
        account_id,
        "INF123",
    )

    transactions = cli_scenario.invoke_json(["transactions", "list"])
    assert len(transactions) == 1
    assert int(transactions[0]["id"]) == transaction_id
    assert transactions[0]["security"]["key"] == "INF123"

    delete_result = cli_scenario.invoke(
        ["transactions", "delete", "--no-input", "--force", str(transaction_id)]
    )
    assert (
        f"Transaction with ID {transaction_id} was deleted successfully."
        in delete_result.output
    )

    list_result = cli_scenario.invoke(["transactions", "list"])
    assert "No transactions found in the database." in list_result.output


def test_transactions_list_respects_limit_and_offset(cli_scenario: CliScenario) -> None:
    """Transaction listing respects pagination and sort order."""
    account_id = cli_scenario.add_account("Primary", "HDFC")
    cli_scenario.add_security("INF123", "Test Fund")
    cli_scenario.add_transaction(
        "2025-01-10",
        "purchase",
        "Older buy",
        "1000.00",
        "10.000",
        account_id,
        "INF123",
    )
    cli_scenario.add_transaction(
        "2025-02-10",
        "purchase",
        "Newer buy",
        "1200.00",
        "11.000",
        account_id,
        "INF123",
    )

    first_page = cli_scenario.invoke_json(["transactions", "list", "--limit", "1"])
    second_page = cli_scenario.invoke_json(
        ["transactions", "list", "--limit", "1", "--offset", "1"]
    )

    assert first_page[0]["description"] == "Newer buy"
    assert second_page[0]["description"] == "Older buy"


def test_transactions_add_requires_all_fields_in_no_input_mode(
    runner: CliRunner,
) -> None:
    """Transactions add must fail in non-interactive mode when args are missing."""
    from niveshpy.cli.main import cli

    result = runner.invoke(
        cli,
        [
            "--no-color",
            "transactions",
            "add",
            "--no-input",
            "2025-01-10",
            "purchase",
        ],
    )

    assert result.exit_code == 1
    assert "Missing required arguments for non-interactive mode" in result.output


def test_transactions_add_with_unknown_security_fails(
    cli_scenario: CliScenario,
) -> None:
    """Transactions fail cleanly when the referenced security does not exist."""
    account_id = cli_scenario.add_account("Primary", "HDFC")

    result = cli_scenario.invoke(
        [
            "transactions",
            "add",
            "--no-input",
            "2025-01-10",
            "purchase",
            "Initial buy",
            "1000.00",
            "10.000",
            str(account_id),
            "UNKNOWN",
        ],
        expected_exit_code=1,
    )

    assert "Security with identifier 'UNKNOWN' not found." in result.output


def test_transactions_delete_requires_force_in_no_input_mode(
    cli_scenario: CliScenario,
) -> None:
    """Transactions delete must fail without --force in non-interactive mode."""
    account_id = cli_scenario.add_account("Primary", "HDFC")
    cli_scenario.add_security("INF123", "Test Fund")
    transaction_id = cli_scenario.add_transaction(
        "2025-01-10",
        "purchase",
        "Initial buy",
        "1000.00",
        "10.000",
        account_id,
        "INF123",
    )

    result = cli_scenario.invoke(
        ["transactions", "delete", "--no-input", str(transaction_id)],
        expected_exit_code=1,
    )

    assert "--force must be provided" in result.output

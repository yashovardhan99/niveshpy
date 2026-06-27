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


def test_all_flag_valid_with_normal_transactions(cli_scenario: CliScenario) -> None:
    """--all flag is valid when invoked with normal transactions."""
    account_id = cli_scenario.add_account("Primary", "HDFC")
    cli_scenario.add_security("INF123", "Test Fund")

    cli_scenario.add_transaction(
        "2025-01-10",
        "purchase",
        "Normal transaction",
        "1000.00",
        "10.000",
        account_id,
        "INF123",
    )

    # --all flag should work (output should be same as without flag for normal transactions)
    result_without_flag = cli_scenario.invoke(["transactions", "list"])
    result_with_flag = cli_scenario.invoke(["transactions", "list", "--all"])

    assert result_without_flag.exit_code == 0
    assert result_with_flag.exit_code == 0
    # Both should have the transaction (check for partial match due to truncated output)
    assert "Norm" in result_without_flag.output
    assert "Norm" in result_with_flag.output


def test_ignored_hidden_by_default(cli_scenario: CliScenario) -> None:
    """Ignored transactions are hidden by default without --all flag."""
    account_id = cli_scenario.add_account("Primary", "HDFC")
    cli_scenario.add_security("INF123", "Test Fund")

    # Add a normal transaction through CLI
    cli_scenario.add_transaction(
        "2025-01-10",
        "purchase",
        "Normal transaction",
        "1000.00",
        "10.000",
        account_id,
        "INF123",
    )

    # Seed an ignored transaction directly to the repository
    cli_scenario.add_ignored_transaction(
        "2025-01-11",
        "purchase",
        "Ignored transaction",
        "500.00",
        "5.000",
        account_id,
        "INF123",
    )

    # Without --all flag, ignored transaction should not be shown
    result = cli_scenario.invoke(["transactions", "list"])
    assert result.exit_code == 0
    assert "Norm" in result.output
    # The ignored transaction's description should NOT appear
    assert "Igno" not in result.output


def test_all_shows_ignored(cli_scenario: CliScenario) -> None:
    """--all flag shows ignored transactions with [IGNORED] marker."""
    account_id = cli_scenario.add_account("Primary", "HDFC")
    cli_scenario.add_security("INF123", "Test Fund")

    # Add a normal transaction through CLI
    cli_scenario.add_transaction(
        "2025-01-10",
        "purchase",
        "Normal transaction",
        "1000.00",
        "10.000",
        account_id,
        "INF123",
    )

    # Seed an ignored transaction directly to the repository
    cli_scenario.add_ignored_transaction(
        "2025-01-11",
        "purchase",
        "Ignored transaction",
        "500.00",
        "5.000",
        account_id,
        "INF123",
    )

    # With --all flag, both should be shown
    result = cli_scenario.invoke(["transactions", "list", "--all"])
    assert result.exit_code == 0
    assert "Norm" in result.output
    assert "Igno" in result.output

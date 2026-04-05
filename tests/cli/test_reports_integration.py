"""Integration tests for report CLI flows."""

from tests.cli.conftest import CliScenario


def _seed_basic_portfolio(cli_scenario: CliScenario) -> None:
    """Seed a small portfolio using CLI commands."""
    account_id = cli_scenario.add_account("Primary", "HDFC")
    cli_scenario.add_security("INF123", "Test Fund")
    cli_scenario.add_security("STK001", "Test Stock", security_type="STOCK")
    cli_scenario.update_price("INF123", "2025-01-15", "101.25")
    cli_scenario.update_price("STK001", "2025-01-15", "250.00")
    cli_scenario.add_transaction(
        "2025-01-10",
        "purchase",
        "Fund buy",
        "1000.00",
        "10.000",
        account_id,
        "INF123",
    )
    cli_scenario.add_transaction(
        "2025-01-12",
        "purchase",
        "Stock buy",
        "500.00",
        "2.000",
        account_id,
        "STK001",
    )


def test_reports_summary_happy_path(cli_scenario: CliScenario) -> None:
    """Summary report returns portfolio metrics and top holdings."""
    _seed_basic_portfolio(cli_scenario)

    summary = cli_scenario.invoke_json(["reports", "summary"])
    assert summary["metrics"]["total_current_value"] == "1512.50"
    assert summary["metrics"]["total_invested"] == "1500.00"
    assert summary["metrics"]["total_gains"] == "12.50"
    assert summary["metrics"]["gains_percentage"] == "0.0083"
    assert len(summary["top_holdings"]) == 2
    assert {holding["security"]["key"] for holding in summary["top_holdings"]} == {
        "INF123",
        "STK001",
    }


def test_reports_holdings_and_performance_happy_paths(
    cli_scenario: CliScenario,
) -> None:
    """Holdings and performance reports return the active positions."""
    _seed_basic_portfolio(cli_scenario)

    holdings = cli_scenario.invoke_json(["reports", "holdings"])
    performance = cli_scenario.invoke_json(["reports", "performance"])

    assert len(holdings) == 2
    assert len(performance) == 2
    holdings_by_key = {h["security"]["key"]: h for h in holdings}
    performance_by_key = {p["security"]["key"]: p for p in performance}

    assert holdings_by_key["INF123"]["account"]["name"] == "Primary"
    assert holdings_by_key["INF123"]["current"] == "1012.50"
    assert holdings_by_key["INF123"]["invested"] == "1000.00"
    assert holdings_by_key["STK001"]["current"] == "500.00"
    assert holdings_by_key["STK001"]["invested"] == "500.00"

    assert performance_by_key["INF123"]["current_value"] == "1012.50"
    assert performance_by_key["INF123"]["invested"] == "1000.00"
    assert performance_by_key["INF123"]["gains"] == "12.50"
    assert performance_by_key["STK001"]["current_value"] == "500.00"
    assert performance_by_key["STK001"]["invested"] == "500.00"
    assert performance_by_key["STK001"]["gains"] == "0.00"


def test_reports_allocation_happy_path(cli_scenario: CliScenario) -> None:
    """Allocation report returns grouped allocation rows for seeded holdings."""
    _seed_basic_portfolio(cli_scenario)

    allocation = cli_scenario.invoke_json(["reports", "allocation"])
    assert len(allocation) == 2

    amount_by_type = {row["security_type"]: row["amount"] for row in allocation}
    assert amount_by_type["mutual_fund"] == "1012.50"
    assert amount_by_type["stock"] == "500.00"

    allocation_sum = sum(float(row["allocation"]) for row in allocation)
    assert round(allocation_sum, 4) == 1.0


def test_reports_summary_with_filters_returns_empty_state_message(
    cli_scenario: CliScenario,
) -> None:
    """Summary should return a no-holdings warning for unmatched filters."""
    result = cli_scenario.invoke(["reports", "summary", "name:does-not-exist"])

    assert "No holdings found for the given filters" in result.output

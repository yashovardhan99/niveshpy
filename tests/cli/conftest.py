"""Shared fixtures and helpers for CLI integration tests."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

import pytest
from click.testing import CliRunner, Result
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from niveshpy.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def cli_in_memory_engine(monkeypatch: pytest.MonkeyPatch):
    """Use an isolated in-memory SQLite engine for CLI integration tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn: sqlite3.Connection, _):
        dbapi_conn.create_function("iregexp", 2, _iregexp)
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    import niveshpy.database as database

    monkeypatch.setattr(database, "_engine", engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_cli_database(cli_in_memory_engine) -> None:
    """Reset the in-memory database between CLI integration tests."""
    from niveshpy.infrastructure.sqlite.models import Account, Security  # noqa: F401
    from niveshpy.models.price import Price  # noqa: F401
    from niveshpy.models.transaction import Transaction  # noqa: F401

    SQLModel.metadata.drop_all(cli_in_memory_engine)
    SQLModel.metadata.create_all(cli_in_memory_engine)


def _iregexp(pattern: str, value: str | None) -> bool:
    """Case-insensitive regex match for SQLite."""
    if value is None:
        return False
    return bool(re.search(pattern, value, re.IGNORECASE))


def parse_json_output(result_output: str) -> Any:
    """Parse CLI output into JSON, tolerating warning text prefixes."""
    stripped = result_output.lstrip()
    decoder = json.JSONDecoder()

    for idx, char in enumerate(stripped):
        if char not in "[{":
            continue
        try:
            parsed, end = decoder.raw_decode(stripped[idx:])
        except json.JSONDecodeError:
            continue

        # Only accept parses that consume the remaining non-whitespace output.
        if stripped[idx + end :].strip() == "":
            return parsed

    raise AssertionError(
        "Expected JSON output but could not parse any valid JSON payload. "
        f"Output was: {result_output!r}"
    )


@dataclass
class CliScenario:
    """Helper for invoking the CLI and seeding test data."""

    runner: CliRunner

    def invoke(self, args: list[str], *, expected_exit_code: int = 0) -> Result:
        """Invoke the CLI with a default no-color flag and assert exit code."""
        result = self.runner.invoke(cli, ["--no-color", *args])
        assert result.exit_code == expected_exit_code, result.output
        return result

    def invoke_json(self, args: list[str]) -> Any:
        """Invoke a CLI command expected to return JSON."""
        result = self.invoke([*args, "--json"])
        return parse_json_output(result.output)

    def add_account(self, name: str, institution: str) -> int:
        """Add an account through the CLI and return its id."""
        self.invoke(["accounts", "add", "--no-input", name, institution])
        accounts = self.invoke_json(["accounts", "list"])
        account = next(
            acc
            for acc in accounts
            if acc["name"] == name and acc["institution"] == institution
        )
        return int(account["id"])

    def add_security(
        self,
        key: str,
        name: str,
        category: str = "EQUITY",
        security_type: str = "MUTUAL_FUND",
    ) -> str:
        """Add a security through the CLI and return its key."""
        self.invoke(
            [
                "securities",
                "add",
                "--no-input",
                key,
                name,
                category,
                security_type,
            ]
        )
        return key

    def update_price(self, key: str, date: str, *ohlc: str) -> None:
        """Update a price through the CLI."""
        self.invoke(["prices", "update", key, date, *ohlc])

    def add_transaction(
        self,
        transaction_date: str,
        transaction_type: str,
        description: str,
        amount: str,
        units: str,
        account_id: int,
        security_key: str,
    ) -> int:
        """Add a transaction through the CLI and return its id."""
        result = self.invoke(
            [
                "transactions",
                "add",
                "--no-input",
                transaction_date,
                transaction_type,
                description,
                amount,
                units,
                str(account_id),
                security_key,
            ]
        )

        match = re.search(r"ID:\s*(\d+)", result.output)
        if match:
            return int(match.group(1))

        # Fallback: deterministic lookup by full identifying tuple.
        transactions = self.invoke_json(["transactions", "list"])
        transaction = next(
            txn
            for txn in transactions
            if txn["transaction_date"] == transaction_date
            and txn["type"] == transaction_type
            and txn["description"] == description
            and txn["amount"] == amount
            and txn["units"] == units
            and int(txn["account"]["id"]) == account_id
            and txn["security"]["key"] == security_key
        )
        return int(transaction["id"])


@pytest.fixture
def cli_scenario(runner: CliRunner) -> CliScenario:
    """Create a scenario helper for CLI integration tests."""
    return CliScenario(runner)

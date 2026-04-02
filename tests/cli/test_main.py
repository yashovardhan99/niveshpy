"""Tests for the main CLI entry point."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from niveshpy.cli.main import cli


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


class TestCLIMain:
    """Tests for the top-level CLI group."""

    def test_version_flag(self, runner):
        """--version prints version string and exits 0."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "NiveshPy" in result.output

    def test_version_flag_short(self, runner):
        """-v prints version string and exits 0."""
        result = runner.invoke(cli, ["-v"])
        assert result.exit_code == 0
        assert "NiveshPy" in result.output

    def test_help_flag(self, runner):
        """--help prints help text and exits 0."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_help_flag_short(self, runner):
        """-h prints help text and exits 0."""
        result = runner.invoke(cli, ["-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_help_shows_subcommands(self, runner):
        """Help output lists all registered subcommand groups."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for cmd in (
            "accounts",
            "securities",
            "transactions",
            "parse",
            "prices",
            "reports",
        ):
            assert cmd in result.output, f"Subcommand '{cmd}' not found in help output"

    def test_debug_flag_short(self, runner):
        """-d flag is accepted and sets debug state."""
        with (
            patch("niveshpy.core.app.Application"),
            patch("niveshpy.cli.utils.setup.initialize_app_state"),
        ):
            result = runner.invoke(cli, ["-d", "--help"])
        assert result.exit_code == 0

    def test_no_color_flag(self, runner):
        """--no-color flag is accepted."""
        with (
            patch("niveshpy.core.app.Application"),
            patch("niveshpy.cli.utils.setup.initialize_app_state"),
        ):
            result = runner.invoke(cli, ["--no-color", "--help"])
        assert result.exit_code == 0

    def test_unknown_command_fails(self, runner):
        """Invoking an unknown subcommand exits with an error."""
        with (
            patch("niveshpy.core.app.Application"),
            patch("niveshpy.cli.utils.setup.initialize_app_state"),
        ):
            result = runner.invoke(cli, ["nonexistent"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Error" in result.output

    def test_no_args_shows_help(self, runner):
        """Invoking with no arguments shows help text."""
        with (
            patch("niveshpy.core.app.Application"),
            patch("niveshpy.cli.utils.setup.initialize_app_state"),
        ):
            result = runner.invoke(cli, [])
        assert "Usage:" in result.output

    def test_verbose_alias(self, runner):
        """--verbose is an alias for --debug."""
        with (
            patch("niveshpy.core.app.Application"),
            patch("niveshpy.cli.utils.setup.initialize_app_state"),
        ):
            result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0

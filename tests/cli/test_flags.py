"""Tests for CLI flag decorators."""

import click
import pytest
from click.testing import CliRunner

from niveshpy.cli.utils import flags
from niveshpy.cli.utils.output import OutputFormat


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


# --- Helper commands decorated with flags ---


@click.command()
@flags.output()
@flags.limit("items")
@flags.offset("items")
def output_limit_offset_cmd(format, limit, offset):
    """Test command with output, limit, and offset flags."""
    click.echo(f"{format},{limit},{offset}")


@click.command()
@flags.output(allowed=[OutputFormat.TABLE, OutputFormat.JSON])
def restricted_output_cmd(format):
    """Test command with restricted output options."""
    click.echo(f"{format}")


@click.command()
@flags.force()
def force_cmd(force):
    """Test command with force flag."""
    click.echo(f"force={force}")


@click.command()
@flags.dry_run()
def dry_run_cmd(dry_run):
    """Test command with dry-run flag."""
    click.echo(f"dry_run={dry_run}")


# --- Test classes ---


class TestOutputFlag:
    """Tests for the output format flag."""

    def test_default_is_table(self, runner):
        """No flag defaults to TABLE format."""
        result = runner.invoke(output_limit_offset_cmd, [])
        assert result.exit_code == 0
        assert result.output.startswith(f"{OutputFormat.TABLE},")

    def test_csv_flag(self, runner):
        """--csv sets format to CSV."""
        result = runner.invoke(output_limit_offset_cmd, ["--csv"])
        assert result.exit_code == 0
        assert f"{OutputFormat.CSV}," in result.output

    def test_json_flag(self, runner):
        """--json sets format to JSON."""
        result = runner.invoke(output_limit_offset_cmd, ["--json"])
        assert result.exit_code == 0
        assert f"{OutputFormat.JSON}," in result.output

    def test_allowed_restricts_options(self, runner):
        """When allowed=[TABLE, JSON], --csv is not available."""
        result = runner.invoke(restricted_output_cmd, ["--csv"])
        assert result.exit_code != 0
        assert "No such option" in result.output or "no such option" in result.output

    def test_allowed_json_still_works(self, runner):
        """When allowed=[TABLE, JSON], --json still works."""
        result = runner.invoke(restricted_output_cmd, ["--json"])
        assert result.exit_code == 0
        assert f"{OutputFormat.JSON}" in result.output


class TestLimitFlag:
    """Tests for the limit flag."""

    def test_default_limit(self, runner):
        """Default limit value is 30."""
        result = runner.invoke(output_limit_offset_cmd, [])
        assert result.exit_code == 0
        parts = result.output.strip().split(",")
        assert parts[1] == "30"

    def test_custom_limit(self, runner):
        """--limit 10 overrides the default."""
        result = runner.invoke(output_limit_offset_cmd, ["--limit", "10"])
        assert result.exit_code == 0
        parts = result.output.strip().split(",")
        assert parts[1] == "10"


class TestOffsetFlag:
    """Tests for the offset flag."""

    def test_default_offset(self, runner):
        """Default offset value is 0."""
        result = runner.invoke(output_limit_offset_cmd, [])
        assert result.exit_code == 0
        parts = result.output.strip().split(",")
        assert parts[2] == "0"

    def test_custom_offset(self, runner):
        """--offset 5 overrides the default."""
        result = runner.invoke(output_limit_offset_cmd, ["--offset", "5"])
        assert result.exit_code == 0
        parts = result.output.strip().split(",")
        assert parts[2] == "5"


class TestOtherFlags:
    """Tests for force and dry-run flags."""

    def test_force_flag(self, runner):
        """--force sets force=True."""
        result = runner.invoke(force_cmd, ["--force"])
        assert result.exit_code == 0
        assert "force=True" in result.output

    def test_force_flag_short(self, runner):
        """-f sets force=True."""
        result = runner.invoke(force_cmd, ["-f"])
        assert result.exit_code == 0
        assert "force=True" in result.output

    def test_force_flag_default(self, runner):
        """No flag defaults force=False."""
        result = runner.invoke(force_cmd, [])
        assert result.exit_code == 0
        assert "force=False" in result.output

    def test_dry_run_flag(self, runner):
        """--dry-run sets dry_run=True."""
        result = runner.invoke(dry_run_cmd, ["--dry-run"])
        assert result.exit_code == 0
        assert "dry_run=True" in result.output

    def test_dry_run_flag_short(self, runner):
        """-n sets dry_run=True."""
        result = runner.invoke(dry_run_cmd, ["-n"])
        assert result.exit_code == 0
        assert "dry_run=True" in result.output

    def test_dry_run_flag_default(self, runner):
        """No flag defaults dry_run=False."""
        result = runner.invoke(dry_run_cmd, [])
        assert result.exit_code == 0
        assert "dry_run=False" in result.output

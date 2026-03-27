"""Tests for CLI error handling in NiveshPyCommand."""

from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from niveshpy.cli.utils.overrides import NiveshPyCommand
from niveshpy.exceptions import (
    NetworkError,
    NiveshPyError,
    OperationError,
    ResourceNotFoundError,
    ValidationError,
)


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


def _make_command(exception):
    """Create a NiveshPyCommand that raises the given exception."""

    @click.command(cls=NiveshPyCommand)
    def cmd():
        raise exception

    return cmd


class TestNiveshPyCommandErrorHandling:
    """Tests for NiveshPyCommand exception catching."""

    def test_catches_niveshpy_error(self, runner):
        """NiveshPyError is caught and results in exit code 1."""
        cmd = _make_command(NiveshPyError("base error"))
        with patch("niveshpy.cli.utils.output.handle_error") as mock_handle_error:
            result = runner.invoke(cmd)
        assert result.exit_code == 1
        mock_handle_error.assert_called_once()

    def test_catches_resource_not_found(self, runner):
        """ResourceNotFoundError is caught and results in exit code 1."""
        cmd = _make_command(ResourceNotFoundError("Account", "123"))
        with patch("niveshpy.cli.utils.output.handle_error") as mock_handle_error:
            result = runner.invoke(cmd)
        assert result.exit_code == 1
        mock_handle_error.assert_called_once()

    def test_catches_operation_error(self, runner):
        """OperationError is caught."""
        cmd = _make_command(OperationError("op failed"))
        with patch("niveshpy.cli.utils.output.handle_error") as mock_handle_error:
            result = runner.invoke(cmd)
        assert result.exit_code == 1
        mock_handle_error.assert_called_once()

    def test_catches_validation_error(self, runner):
        """ValidationError is caught."""
        cmd = _make_command(ValidationError("bad input"))
        with patch("niveshpy.cli.utils.output.handle_error") as mock_handle_error:
            result = runner.invoke(cmd)
        assert result.exit_code == 1
        mock_handle_error.assert_called_once()

    def test_catches_network_error(self, runner):
        """NetworkError is caught."""
        cmd = _make_command(NetworkError("connection refused"))
        with patch("niveshpy.cli.utils.output.handle_error") as mock_handle_error:
            result = runner.invoke(cmd)
        assert result.exit_code == 1
        mock_handle_error.assert_called_once()

    def test_non_niveshpy_error_propagates(self, runner):
        """Non-NiveshPyError exceptions are NOT caught and propagate."""
        cmd = _make_command(ValueError("unexpected"))
        result = runner.invoke(cmd)
        # Click catches unhandled exceptions and sets exit_code=1, but the
        # traceback should appear in the output (exception not silenced).
        assert result.exit_code != 0
        assert result.exception is not None
        assert isinstance(result.exception, ValueError)

    def test_error_message_in_handle_error(self, runner):
        """The original exception is passed to handle_error."""
        error = NiveshPyError("specific error message")
        cmd = _make_command(error)
        with patch("niveshpy.cli.utils.output.handle_error") as mock_handle_error:
            runner.invoke(cmd)
        passed_error = mock_handle_error.call_args[0][0]
        assert passed_error.message == "specific error message"

    def test_exit_code_is_1(self, runner):
        """Exit code is exactly 1 on NiveshPyError."""
        cmd = _make_command(NiveshPyError("fail"))
        with patch("niveshpy.cli.utils.output.handle_error"):
            result = runner.invoke(cmd)
        assert result.exit_code == 1

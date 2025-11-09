"""Overrides for common click decorators."""

from collections.abc import Callable
from typing import Any, TypeVar

import click

from niveshpy.cli.utils import output
from niveshpy.exceptions import NiveshPyError

_AnyCallable = Callable[..., Any]
FC = TypeVar("FC", bound="_AnyCallable | click.Command")


def group(*args, **kwargs) -> click.Group:
    """Create a Click command group with common settings."""
    _set_common_options(kwargs)
    kwargs.setdefault("subcommand_metavar", "<command>")
    return click.group(*args, **kwargs)


def _set_common_options(kwargs):
    kwargs.setdefault("context_settings", {})
    kwargs["context_settings"].setdefault("help_option_names", ["-h", "--help"])
    kwargs.setdefault("options_metavar", "[options]")


class NiveshPyCommand(click.Command):
    """Custom Click Command with common settings."""

    def invoke(self, ctx):
        """Invoke the command with error handling."""
        try:
            return super().invoke(ctx)
        except NiveshPyError as e:
            output.handle_error(e)
            ctx.exit(1)


def command(*args, **kwargs) -> Callable[[_AnyCallable], NiveshPyCommand]:
    """Create a Click command with common settings."""
    _set_common_options(kwargs)

    return click.command(*args, **kwargs, cls=NiveshPyCommand)

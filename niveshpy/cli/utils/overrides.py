"""Overrides for common click decorators."""

from collections.abc import Callable
from typing import Any

import click

from niveshpy.exceptions import NiveshPyError

_AnyCallable = Callable[..., Any]


class NiveshPyCommand(click.Command):
    """Custom Click Command with common settings."""

    def invoke(self, ctx):
        """Invoke the command with error handling."""
        try:
            return super().invoke(ctx)
        except NiveshPyError as e:
            from niveshpy.cli.utils import output

            output.handle_error(e)
            ctx.exit(1)


def command(*args, **kwargs) -> Callable[[_AnyCallable], NiveshPyCommand]:
    """Create a Click command with common settings."""
    from niveshpy.cli.utils import essentials

    essentials.set_common_options(kwargs)

    return click.command(*args, **kwargs, cls=NiveshPyCommand)

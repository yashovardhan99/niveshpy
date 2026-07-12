"""Essential utilities for the CLI."""

from collections.abc import Callable
from functools import cached_property
from importlib import import_module
from typing import Any

import click

from niveshpy.exceptions import NiveshPyError


class LazyCommand(click.Command):
    """A lazy click command.

    A click Command that imports the actual implementation only when
    needed.  This allows for more resilient CLIs where the top-level
    command does not fail when a subcommand is broken enough to fail
    at import time.
    """

    def __init__(self, import_name, **kwargs):
        """Initialize the lazy command."""
        self._import_name = import_name
        super().__init__(**kwargs)

    @cached_property
    def _impl(self):
        module, name = self._import_name.split(":", 1)
        return getattr(import_module(module), name)

    def invoke(self, ctx):
        """Invoke the command."""
        try:
            return self._impl.invoke(ctx)
        except NiveshPyError as e:
            from niveshpy.cli.utils import output

            output.handle_error(e)
            ctx.exit(1)

    def get_usage(self, ctx):
        """Get the usage string."""
        return self._impl.get_usage(ctx)

    def get_params(self, ctx):
        """Get the parameters."""
        return self._impl.get_params(ctx)


_AnyCallable = Callable[..., Any]


def command(
    name: str | None = None,
    cls: type[click.Command] | None = None,
    parent: click.Group | None = None,
    **kwargs,
) -> Callable[[_AnyCallable], click.Command]:
    """Create a Click command with common settings."""
    set_common_options(kwargs)

    if parent is not None:
        return parent.command(name, cls, **kwargs)
    else:
        return click.command(name, cls, **kwargs)


class LazyGroup(click.Group):
    """A lazy click group.

    A click Group that imports the actual implementation only when
    needed.  This allows for more resilient CLIs where the top-level
    command does not fail when a subcommand is broken enough to fail
    at import time.
    """

    def __init__(self, import_name, **kwargs):
        """Initialize the lazy group."""
        self._import_name = import_name
        super().__init__(**kwargs)

    @cached_property
    def _impl(self):
        module, name = self._import_name.split(":", 1)
        return getattr(import_module(module), name)

    def get_command(self, ctx, cmd_name):
        """Get a command by name."""
        return self._impl.get_command(ctx, cmd_name)

    def list_commands(self, ctx):
        """List all commands."""
        return self._impl.list_commands(ctx)

    def invoke(self, ctx):
        """Invoke the command."""
        return self._impl.invoke(ctx)

    def get_usage(self, ctx):
        """Get the usage string."""
        return self._impl.get_usage(ctx)

    def get_params(self, ctx):
        """Get the parameters."""
        return self._impl.get_params(ctx)


def group(
    name: str | None = None,
    cls: type[click.decorators.GrpType] | None = None,
    parent: click.Group | None = None,
    **kwargs,
) -> click.Group | Callable[[Any], click.Group | click.decorators.GrpType]:
    """Create a Click command group with common settings."""
    set_common_options(kwargs)
    kwargs.setdefault("subcommand_metavar", "<command>")
    if parent is not None:
        return parent.group(name, cls=cls, **kwargs)
    else:
        return click.group(name, cls=cls, **kwargs)


def set_common_options(kwargs):
    """Set common options for Click commands and groups."""
    kwargs.setdefault("context_settings", {})
    kwargs["context_settings"].setdefault("help_option_names", ["-h", "--help"])
    kwargs.setdefault("options_metavar", "[options]")

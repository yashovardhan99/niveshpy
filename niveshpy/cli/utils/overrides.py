"""Overrides for common click decorators."""

from collections.abc import Callable
from typing import Any, TypeVar
import click


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


def command(*args, **kwargs) -> click.Command:
    """Create a Click command with common settings."""
    _set_common_options(kwargs)

    return click.command(*args, **kwargs)

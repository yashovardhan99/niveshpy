"""Common flags for CLI commands."""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

import click

from niveshpy.cli.utils.output import OutputFormat
from niveshpy.core.app import AppState
from niveshpy.core.logging import logger

_AnyCallable = Callable[..., Any]
FC = TypeVar("FC", bound="_AnyCallable | click.Command")


def limit(name: str, default: int = 30) -> Callable[[FC], FC]:
    """Common limit option for CLI commands."""
    return click.option(
        "--limit",
        "-l",
        default=default,
        help=f"Maximum number of {name} to list.",
        show_default=True,
    )


def offset(name: str, default: int = 0) -> Callable[[FC], FC]:
    """Common offset option for CLI commands."""
    return click.option(
        "--offset",
        default=default,
        help=f"Number of {name} to skip before starting to list. Use with --limit for pagination.",
        show_default=True,
    )


def _callback(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    """Callback to handle common flag."""
    logger.debug("Flag %s set to %s", param.name, value)
    if not ctx.resilient_parsing:
        state = ctx.ensure_object(AppState)
        if param.name == "no_input" and value:
            state.no_input = value
        elif param.name == "debug" and value:
            state.debug = value
        elif param.name == "no_color" and value:
            state.no_color = value
    return value


def no_input() -> Callable[[FC], FC]:
    """Common no-input option for CLI commands."""
    return click.option(
        "--no-input",
        is_flag=True,
        help="Run without user input, using defaults or skipping prompts.",
        expose_value=False,
        callback=_callback,
    )


def force() -> Callable[[FC], FC]:
    """Common force option for CLI commands."""
    return click.option(
        "--force",
        "-f",
        is_flag=True,
        help="Force the operation without confirmation.",
    )


def dry_run() -> Callable[[FC], FC]:
    """Common dry-run option for CLI commands."""
    return click.option(
        "--dry-run",
        "-n",
        is_flag=True,
        help="Simulate the operation without making any changes.",
    )


def debug() -> Callable[[FC], FC]:
    """Common debug/verbose option for CLI commands."""
    return click.option(
        "--debug",
        "--verbose",
        "-d",
        is_flag=True,
        help="Enable verbose logging.",
        expose_value=False,
        callback=_callback,
        envvar=("NIVESHPY_DEBUG", "DEBUG"),
    )


def no_color() -> Callable[[FC], FC]:
    """Common no-color option for CLI commands."""
    return click.option(
        "--no-color",
        is_flag=True,
        help="Disable colored output.",
        expose_value=False,
        callback=_callback,
        envvar=("NIVESHPY_NO_COLOR", "NO_COLOR"),
    )


def output(name: str = "output") -> Callable[[FC], FC]:
    """Common output option for CLI commands."""
    options = [
        click.option(
            "--csv",
            name,
            flag_value=OutputFormat.CSV,
        ),
        click.option(
            "--json",
            name,
            flag_value=OutputFormat.JSON,
        ),
        click.option(
            "--table",
            name,
            flag_value=OutputFormat.TABLE,
            default=True,
            hidden=True,
        ),
    ]
    return functools.partial(functools.reduce, lambda x, opt: opt(x), options)

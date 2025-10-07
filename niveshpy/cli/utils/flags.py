"""Common flags for CLI commands."""

import functools
from typing import Any, TypeVar
from collections.abc import Callable
import click

from niveshpy.cli.app import AppState

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


def _callback(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    """Callback to handle common flag."""
    if not ctx.resilient_parsing:
        state = ctx.ensure_object(AppState)
        if param.name == "no_input" and value:
            print("Running in no-input mode.")
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
        "-N",
        is_flag=True,
        help="Run without user input, using defaults or skipping prompts.",
        expose_value=False,
        callback=_callback,
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


def common_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Apply common options to a Click command."""
    options = [
        click.version_option(None, "--version", "-v", prog_name="NiveshPy"),
    ]
    return functools.reduce(lambda x, opt: opt(x), options, f)

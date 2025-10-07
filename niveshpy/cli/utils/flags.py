"""Common flags for CLI commands."""

import functools
from typing import Any, TypeVar
from collections.abc import Callable
import click

from niveshpy.cli.app import AppState

_AnyCallable = Callable[..., Any]
FC = TypeVar("FC", bound="_AnyCallable | click.Command")


def option_limit(name: str, default: int = 30) -> Callable[[FC], FC]:
    """Common limit option for CLI commands."""
    return click.option(
        "--limit",
        "-l",
        default=default,
        help=f"Maximum number of {name} to list.",
        show_default=True,
    )


def callback(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    """Callback to handle common flag."""
    if not ctx.resilient_parsing:
        ctx.ensure_object(AppState)
        if param.name == "no_input":
            ctx.obj.no_input = value
    return value


def common_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Apply common options to a Click command."""
    options = [
        click.option(
            "--no-input",
            "-N",
            is_flag=True,
            help="Run without user input, using defaults or skipping prompts.",
            expose_value=False,
            callback=callback,
        )
    ]
    return functools.reduce(lambda x, opt: opt(x), options, f)

"""Utility functions for styling CLI output."""

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum, auto
from itertools import starmap, zip_longest
from niveshpy.cli.utils import logging
from typing import Literal
from collections.abc import Callable, Generator
import click
from rich.console import Console
from rich import box, progress

from collections.abc import Sequence
import polars as pl
from rich.table import Table

from niveshpy.core.app import AppState

_console = Console()  # Global console instance for utility functions
_error_console = Console(stderr=True)  # Console for error messages


FormatMap = Sequence[str | Callable[[str], str] | None]


class OutputFormat(StrEnum):
    """Enumeration of supported output formats."""

    TABLE = auto()
    CSV = auto()
    JSON = auto()


def _format_as_csv(df: pl.DataFrame, separator: str = ",") -> str:
    """Convert a Polars DataFrame to CSV format, handling nested types appropriately."""
    for col, dtype in df.collect_schema().items():
        if dtype.is_nested():
            if dtype == pl.Struct:
                df = df.with_columns(pl.col(col).struct.json_encode().alias(col))
            elif dtype == pl.List(pl.Struct({"key": pl.Utf8, "value": pl.Utf8})):
                df = df.with_columns(
                    pl.col(col)
                    .list.eval(
                        pl.concat_str(
                            pl.element().struct.field("key"),
                            pl.lit(":"),
                            pl.element().struct.field("value"),
                        )
                    )
                    .list.join(";")
                    .alias(col)
                )
            elif dtype == pl.List(pl.Struct):
                df = df.with_columns(
                    pl.col(col)
                    .list.eval(pl.element().struct.json_encode())
                    .list.join(";")
                    .alias(col)
                )
            elif dtype == pl.List:
                df = df.with_columns(
                    pl.col(col)
                    .list.eval(pl.element().cast(pl.Utf8))
                    .list.join(";")
                    .alias(col)
                )
            else:
                df = df.with_columns(pl.col(col).cast(pl.Utf8).alias(col))
    return df.write_csv(separator=separator)


def _format_dataframe(
    df: pl.DataFrame,
    fmt: OutputFormat,
    fmt_map: FormatMap | None = None,
) -> str | Table:
    """Format a Polars DataFrame according to the specified output format."""
    if fmt == OutputFormat.CSV:
        return _format_as_csv(df)
    elif fmt == OutputFormat.JSON:
        return df.write_json()
    else:
        return (
            _convert_polars_to_rich_table(df, fmt_map)
            if _console.is_terminal
            else _format_as_csv(df, separator="\t")
        )


def _format_datetime(dt: datetime) -> str:
    """Format a datetime object to a relative time string.

    If the datetime is within 7 days, it shows relative time (e.g., "about 3 hours ago").
    If older than 7 days, it shows the absolute date (e.g., "on Jan 01, 2023").

    Args:
        dt (datetime): The datetime object to format.

    Returns:
        str: A human-readable relative time string.

    """
    now = datetime.now()
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"about {seconds} seconds ago"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"about {minutes} minutes ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"about {hours} hours ago"
    else:
        days = seconds // 86400
        if days < 7:
            return f"about {days} days ago"
        else:
            date = dt.strftime("%d %b %Y")
            return f"on {date}"


def _format_list_or_dict(data: list | dict) -> str:
    """Format a list or dictionary into a pretty-printed string."""
    # For empty list or dict, return empty string
    if not data:
        return ""

    # If it is a dictionary with "key" and "value" as keys, convert to a simple key-value pair
    if isinstance(data, dict) and set(data.keys()) == {"key", "value"}:
        return f"{data['key']}: {data['value']}"

    # If it is a list of such dictionaries, format each item recursively
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        formatted_items = [_format_list_or_dict(item) for item in data]
        return ", ".join(formatted_items)

    # Fallback to string representation
    return str(data)


def _convert_polars_to_rich_table(df: pl.DataFrame, fmt_map: FormatMap | None) -> Table:
    """Convert a Polars DataFrame to a Rich Table for pretty printing."""
    table = Table(header_style="dim", box=box.SIMPLE)
    for i, (col, dtype) in enumerate(df.schema.to_python().items()):
        style = fmt_map[i] if fmt_map and i < len(fmt_map) else None
        style = style if isinstance(style, str) else None
        justify: Literal["left", "right"] = (
            "right" if dtype in (int, float, Decimal) else "left"
        )

        table.add_column(col.upper(), justify=justify, style=style)

    def mapper(data: object, fmt: str | None | Callable[[str], str]) -> str:
        if isinstance(data, datetime):
            data_str = _format_datetime(data)
        elif isinstance(data, date):
            data_str = data.strftime("%d %b %Y")
        elif isinstance(data, list | dict):
            data_str = _format_list_or_dict(data)
        else:
            data_str = str(data)

        if fmt is None:
            return data_str
        elif callable(fmt):
            return fmt(data_str)
        else:
            return data_str

    for row in df.iter_rows():
        if fmt_map is None:
            table.add_row(*map(str, row))
        else:
            table.add_row(*starmap(mapper, zip_longest(row, fmt_map, fillvalue=None)))

    return table


def display_message(*objects: object) -> None:
    """Display a general message to the console."""
    _console.print(*objects)


def display_success(message: str) -> None:
    """Display a success message to the console."""
    _console.print(message, style="green")


def display_warning(message: str) -> None:
    """Display a warning message to the error console."""
    _error_console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def display_error(message: str) -> None:
    """Display an error message to the error console."""
    _error_console.print(f"[bold red]Error:[/bold red] {message}")


@contextmanager
def loading_spinner(message: str) -> Generator[None, None, None]:
    """Context manager to show a loading spinner with a message."""
    if _error_console.is_terminal:
        with _error_console.status(message):
            yield
    else:
        yield


def display_dataframe(
    df: pl.DataFrame,
    fmt: OutputFormat,
    fmt_map: FormatMap | None = None,
    extra_message: str | None = None,
) -> None:
    """Display a Polars DataFrame to the console in the specified format using a pager (if in a terminal).

    If the console is a terminal, the output is displayed using a pager for better readability.

    If an extra message is provided, it is displayed before the DataFrame, provided the console is a terminal.

    Args:
        df (pl.DataFrame): The DataFrame to display.
        fmt (OutputFormat): The desired output format (TABLE, CSV, JSON).
        fmt_map (FormatMap | None): Optional formatting map for columns.
        extra_message (str | None): An optional message to display before the DataFrame.
    """
    formatted_data = _format_dataframe(df, fmt, fmt_map)
    if _console.is_terminal:
        with _console.capture() as capture:
            if extra_message:
                _console.print(extra_message)
            _console.print(formatted_data)
        click.echo_via_pager(capture.get())
    else:
        if extra_message:
            _console.print(extra_message)
        _console.print(formatted_data, soft_wrap=True)


def ask_password(prompt: str = "Enter password: ") -> str:
    """Prompt the user for a password securely.

    Args:
        prompt (str): The prompt message to display.

    Returns:
        str: The password entered by the user.
    """
    return _console.input(prompt, password=True).strip()


def get_progress_bar() -> progress.Progress:
    """Create and return a Rich Progress bar instance for displaying progress."""
    return progress.Progress(
        progress.TextColumn("[progress.description]{task.description}"),
        progress.SpinnerColumn(),
        progress.MofNCompleteColumn(),
        progress.TimeElapsedColumn(),
        console=_error_console,
        disable=not _error_console.is_terminal,
    )


def initialize_app_state(state: AppState) -> None:
    """Initialize the application state for CLI operations.

    This function sets up the application state by determining interactivity,
    color settings, and initializing logging.

    Args:
        state (AppState): The application state object to initialize.
    """
    if not state.no_input:
        # If no_input is not set, determine interactivity from console
        state.no_input = not _console.is_interactive

    if state.no_color:
        _console.no_color = True
        _error_console.no_color = True

    logging.setup(state.debug, _error_console)  # Initialize logging with debug flag

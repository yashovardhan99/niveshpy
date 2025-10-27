"""Utility functions for styling CLI output."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum, auto
from itertools import starmap, zip_longest
from typing import Any, Literal
from collections.abc import Callable
import click
from rich.console import Console
from rich import box

from collections.abc import Sequence
import polars as pl
from rich.table import Table

console = Console()  # Global console instance for utility functions
error_console = Console(stderr=True)  # Console for error messages


class OutputFormat(StrEnum):
    """Enumeration of supported output formats."""

    TABLE = auto()
    CSV = auto()
    JSON = auto()


def output_formatted_data(
    content: Any, format: OutputFormat, message: str | None = None
) -> None:
    """Output formatted data to the console, using a pager if in a terminal."""
    if console.is_terminal:
        with console.capture() as capture:
            if message:
                console.print(message, style="yellow")
            console.print_json(
                content
            ) if format == OutputFormat.JSON else console.print(content)
        click.echo_via_pager(capture.get())
    else:
        console.print_json(content) if format == OutputFormat.JSON else console.print(
            content, soft_wrap=True
        )


def format_as_csv(df: pl.DataFrame, separator: str = ",") -> str:
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


def format_dataframe(
    df: pl.DataFrame,
    fmt: OutputFormat,
    fmt_map: Sequence[str | Callable[[str], str] | None] | None = None,
) -> str | Table:
    """Format a Polars DataFrame according to the specified output format."""
    if fmt == OutputFormat.CSV:
        return format_as_csv(df)
    elif fmt == OutputFormat.JSON:
        return df.write_json()
    else:
        return (
            convert_polars_to_rich_table(df, fmt_map)
            if console.is_terminal
            else format_as_csv(df, separator="\t")
        )


def format_datetime(dt: datetime) -> str:
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


def format_list_or_dict(data: list | dict) -> str:
    """Format a list or dictionary into a pretty-printed string."""
    # For empty list or dict, return empty string
    if not data:
        return ""

    # If it is a dictionary with "key" and "value" as keys, convert to a simple key-value pair
    if isinstance(data, dict) and set(data.keys()) == {"key", "value"}:
        return f"{data['key']}: {data['value']}"

    # If it is a list of such dictionaries, format each item recursively
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        formatted_items = [format_list_or_dict(item) for item in data]
        return ", ".join(formatted_items)

    # Fallback to string representation
    return str(data)


def convert_polars_to_rich_table(
    df: pl.DataFrame, fmt_map: Sequence[str | Callable[[str], str] | None] | None
) -> Table:
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
            data_str = format_datetime(data)
        elif isinstance(data, date):
            data_str = data.strftime("%d %b %Y")
        elif isinstance(data, list | dict):
            data_str = format_list_or_dict(data)
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

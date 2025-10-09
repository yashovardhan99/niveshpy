"""Utility functions for styling CLI output."""

from decimal import Decimal
from enum import StrEnum, auto
from itertools import starmap, zip_longest
from typing import Literal
from collections.abc import Callable
import click
from rich.console import Console
from rich import box

from collections.abc import Generator, Sequence
from contextlib import contextmanager
import polars as pl
from rich.table import Table

console = Console()  # Global console instance for utility functions
error_console = Console(stderr=True)  # Console for error messages


@contextmanager
def rich_click_pager(console: "Console") -> Generator[None, None, None]:
    """Context manager to capture and display rich output in a pager via click."""
    with console.capture() as capture:
        yield
    if console.is_terminal:
        click.echo_via_pager(capture.get())
    else:
        console.print(capture.get())


def get_polars_print_config() -> pl.Config:
    """Get Polars print configuration for consistent DataFrame display."""
    return pl.Config(
        tbl_rows=-1,
        tbl_cols=-1,
        tbl_hide_column_data_types=True,
        tbl_hide_dataframe_shape=True,
        tbl_formatting="UTF8_BORDERS_ONLY",
        tbl_width_chars=-1,
    )


class OutputFormat(StrEnum):
    """Enumeration of supported output formats."""

    TABLE = auto()
    CSV = auto()
    JSON = auto()


def format_dataframe(
    df: pl.DataFrame,
    fmt: OutputFormat,
    fmt_map: Sequence[str | Callable[[str], str] | None] | None = None,
) -> str | Table:
    """Format a Polars DataFrame according to the specified output format."""
    if fmt == OutputFormat.CSV:
        return df.write_csv()
    elif fmt == OutputFormat.JSON:
        return df.write_json()
    else:
        return (
            convert_polars_to_rich_table(df, fmt_map)
            if console.is_terminal
            else df.write_csv(separator="\t")
        )


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
        if fmt is None:
            return str(data)
        elif callable(fmt):
            return fmt(str(data))
        else:
            return str(data)

    for row in df.iter_rows():
        if fmt_map is None:
            table.add_row(*map(str, row))
        else:
            table.add_row(*starmap(mapper, zip_longest(row, fmt_map, fillvalue=None)))

    return table

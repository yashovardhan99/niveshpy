"""Utility functions for styling CLI output."""

from decimal import Decimal
from enum import StrEnum, auto
import click
from rich.console import Console


from collections.abc import Generator
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


def format_dataframe(df: pl.DataFrame, fmt: OutputFormat) -> str | Table:
    """Format a Polars DataFrame according to the specified output format."""
    if fmt == OutputFormat.CSV:
        return df.write_csv()
    elif fmt == OutputFormat.JSON:
        return df.write_json()
    else:
        with get_polars_print_config():
            return (
                convert_polars_to_rich_table(df)
                if console.is_terminal
                else df.write_csv(separator="\t")
            )


def convert_polars_to_rich_table(df: pl.DataFrame) -> Table:
    """Convert a Polars DataFrame to a Rich Table for pretty printing."""
    table = Table()
    for col, dtype in df.schema.to_python().items():
        if dtype in (int, float, Decimal):
            table.add_column(col, justify="right")
        else:
            table.add_column(col)

    for row in df.iter_rows():
        table.add_row(*map(str, row))

    return table

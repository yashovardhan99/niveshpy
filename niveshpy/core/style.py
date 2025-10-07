"""Utilities for styling outputs in NiveshPy."""

from contextlib import contextmanager
from typing import TYPE_CHECKING
from collections.abc import Generator
import polars as pl


if TYPE_CHECKING:
    from rich.console import Console


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


@contextmanager
def rich_click_pager(console: "Console") -> Generator[None, None, None]:
    """Context manager to capture and display rich output in a pager via click."""
    import click

    with console.capture() as capture:
        yield
    click.echo_via_pager(capture.get())

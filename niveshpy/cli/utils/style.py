"""Utility functions for styling CLI output."""

import click
from rich.console import Console


from collections.abc import Generator
from contextlib import contextmanager


@contextmanager
def rich_click_pager(console: "Console") -> Generator[None, None, None]:
    """Context manager to capture and display rich output in a pager via click."""
    with console.capture() as capture:
        yield
    click.echo_via_pager(capture.get())

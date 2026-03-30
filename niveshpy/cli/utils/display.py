"""Simple utilities for displaying output in the CLI."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console

# Simple printing utilities for the CLI, using Rich for styling and formatting.


def display(
    *objects: object, console: Console | None = None, style: str | None = None
) -> None:
    """Display objects to the console with optional styling."""
    if not console:
        from niveshpy.cli.utils.setup import _console

        console = _console

    console.print(*objects, style=style)


def display_json(
    json: str | None = None, *, data: Any | None = None, console: Console | None = None
) -> None:
    """Display JSON data to the console with pretty formatting."""
    if not console:
        from niveshpy.cli.utils.setup import _console

        console = _console

    console.print_json(json, data=data)


def display_success(message: str, console: Console | None = None) -> None:
    """Display a success message to the console."""
    display(message, console=console, style="green")


def display_warning(*objects: object, console: Console | None = None) -> None:
    """Display a warning message to the error console."""
    if not console:
        from niveshpy.cli.utils.setup import _error_console

        console = _error_console

    display("[bold yellow]Warning:[/bold yellow]", *objects, console=console)


def display_error(
    *objects: object, tag: str = "Error:", console: Console | None = None
) -> None:
    """Display an error message to the error console."""
    if not console:
        from niveshpy.cli.utils.setup import _error_console

        console = _error_console

    display(f"[bold red]{tag}[/bold red]", *objects, console=console)


# Additional utilities for the CLI.


@contextmanager
def capture_for_pager(console: Console | None = None) -> Generator[None, None, None]:
    """Context manager to capture console output for paging if the console is a terminal."""
    if not console:
        from niveshpy.cli.utils.setup import _console

        console = _console

    if console.is_terminal:
        import click

        with console.capture() as capture:
            yield
        click.echo_via_pager(capture.get())
    else:
        yield


@contextmanager
def loading_spinner(
    message: str, console: Console | None = None
) -> Generator[None, None, None]:
    """Context manager to show a loading spinner with a message."""
    if not console:
        from niveshpy.cli.utils.setup import _error_console

        console = _error_console

    if console.is_terminal:
        with console.status(message):
            yield
    else:
        yield


# Input utilities for the CLI.


def ask_password(prompt: str = "Enter password: ") -> str:
    """Prompt the user for a password securely.

    Args:
        prompt (str): The prompt message to display.

    Returns:
        str: The password entered by the user.
    """
    from niveshpy.cli.utils.setup import _console

    return _console.input(prompt, password=True).strip()

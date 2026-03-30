"""Simple utilities for displaying output in the CLI."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console


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


def ask_password(prompt: str = "Enter password: ") -> str:
    """Prompt the user for a password securely.

    Args:
        prompt (str): The prompt message to display.

    Returns:
        str: The password entered by the user.
    """
    from niveshpy.cli.utils.setup import _console

    return _console.input(prompt, password=True).strip()

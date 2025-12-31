"""Utility functions for styling CLI output."""

import csv
from collections.abc import Callable, Generator, MutableMapping, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from enum import StrEnum, auto
from io import StringIO
from typing import TypeVar

import click
from pydantic import BaseModel, RootModel
from pydantic.fields import FieldInfo
from rich import box, progress
from rich.console import Console
from rich.table import Table

from niveshpy.cli.utils import logging
from niveshpy.core.app import AppState
from niveshpy.core.logging import logger
from niveshpy.exceptions import NiveshPyError
from niveshpy.models.output import BaseMessage, Message, ProgressUpdate, Warning

_console = Console()  # Global console instance for utility functions
_error_console = Console(stderr=True)  # Console for error messages


FormatMap = Sequence[str | Callable[[str], str] | None]


class OutputFormat(StrEnum):
    """Enumeration of supported output formats."""

    TABLE = auto()
    CSV = auto()
    JSON = auto()


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


def _convert_models_to_rich_table(
    items: Sequence[BaseModel], schema: dict[str, FieldInfo]
) -> Table:
    """Convert a list of Pydantic models to a Rich Table for pretty printing."""
    table = Table(header_style="dim", box=box.SIMPLE)
    filtered_fields = filter(
        lambda x: not (schema[x].json_schema_extra or {}).get("hidden", False),  # type: ignore
        schema.keys(),
    )
    ordered_fields = sorted(
        filtered_fields,
        key=lambda x: (schema[x].json_schema_extra or {}).get("order", 0),  # type: ignore
    )
    for field_name in ordered_fields:
        field_info = schema[field_name]
        extras: dict = field_info.json_schema_extra or {}  # type: ignore
        table.add_column(
            field_info.title or field_name.capitalize(),
            justify=extras.get("justify", "left"),
            style=extras.get("style") if isinstance(extras.get("style"), str) else None,
        )

    def mapper(data: object, fmt: Callable[[str], str] | None) -> str:
        if isinstance(data, datetime):
            data_str = _format_datetime(data)
        elif isinstance(data, date):
            data_str = data.strftime("%d %b %Y")
        else:
            data_str = str(data)

        if fmt is None:
            return data_str
        elif callable(fmt):
            return fmt(data_str)
        else:
            return data_str

    for item in items:
        row = []
        for field_name in ordered_fields:
            fmt = None
            extras: dict = schema[field_name].json_schema_extra or {}  # type: ignore
            fmt = extras.get("formatter") if callable(extras.get("formatter")) else None
            value = getattr(item, field_name)
            row.append(mapper(value, fmt))
        table.add_row(*row)

    return table


def display_message(*objects: object, console: Console | None = None) -> None:
    """Display a general message to the console."""
    (console or _console).print(*objects)


def display_success(message: str, console: Console | None = None) -> None:
    """Display a success message to the console."""
    (console or _console).print(message, style="green")


def display_warning(message: object, console: Console | None = None) -> None:
    """Display a warning message to the error console."""
    (console or _error_console).print("[bold yellow]Warning:[/bold yellow]", message)


def display_error(
    message: str, tag: str = "Error:", console: Console | None = None
) -> None:
    """Display an error message to the error console."""
    (console or _error_console).print(f"[bold red]{tag}[/bold red] {message}")


@contextmanager
def loading_spinner(
    message: str, console: Console | None = None
) -> Generator[None, None, None]:
    """Context manager to show a loading spinner with a message."""
    if (console or _error_console).is_terminal:
        with (console or _error_console).status(message):
            yield
    else:
        yield


T = TypeVar("T", bound=BaseModel)


def display_list(
    cls: type[T],
    items: Sequence[T],
    fmt: OutputFormat,
    extra_message: str | None = None,
) -> None:
    """Display a list of items to the console in the specified format.

    If the console is a terminal, the output is displayed using a pager for better readability.

    Args:
        cls: The class type of the models in the list.
        items (Sequence): The list of items to display.
        fmt (OutputFormat): The desired output format (TABLE, CSV, JSON).
        extra_message (str | None): An optional message to display before the list.
    """
    formatted_data: str | Table

    root_model = RootModel[Sequence[T]](items)
    if fmt == OutputFormat.JSON:
        formatted_data = root_model.model_dump_json(indent=4)
    elif fmt == OutputFormat.CSV:
        headers = sorted(
            cls.model_fields.keys(),
            key=lambda x: (cls.model_fields[x].json_schema_extra or {}).get("order", 0),  # type: ignore
        )

        f = StringIO()

        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(root_model.model_dump())

        formatted_data = f.getvalue()
    else:
        formatted_data = _convert_models_to_rich_table(items, cls.model_fields)

    if _console.is_terminal:
        with _console.capture() as capture:
            if extra_message:
                _console.print(extra_message)
            if fmt == OutputFormat.JSON:
                _console.print_json(str(formatted_data))
            else:
                _console.print(formatted_data)
        click.echo_via_pager(capture.get())
    else:
        if fmt == OutputFormat.JSON:
            _console.print_json(str(formatted_data))
        else:
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


def update_progress_bar(
    progress_bar: progress.Progress,
    task_map: MutableMapping[str, progress.TaskID],
    update: ProgressUpdate,
) -> None:
    """Update the progress bar for a given stage.

    Args:
        progress_bar (progress.Progress): The Rich Progress bar instance.
        task_map (MutableMapping[str, progress.TaskID]): A mapping of stage names to task IDs.
        update (ProgressUpdate): The progress update information.
    """
    if update.stage not in task_map:
        task_map[update.stage] = progress_bar.add_task(
            update.description,
            start=True,
            total=update.total,
            completed=update.current if update.current is not None else 0,
        )
    else:
        progress_bar.update(
            task_map[update.stage],
            total=update.total,
            completed=update.current,
            description=update.description,
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


def handle_error(error: NiveshPyError) -> None:
    """Handle and display errors in the CLI.

    Args:
        error (NiveshPyError): The error to handle.
    """
    logger.info(
        "An error of type %s occurred: %s",
        type(error).__name__,
        error.message,
        exc_info=True,
    )
    display_error(error.message)


def handle_niveshpy_message(
    message: BaseMessage, console: Console | None = None
) -> None:
    """Handle and display NiveshPy messages in the CLI.

    Args:
        message (BaseMessage): The message to handle.
        console (Console | None): Optional Rich Console to use for output.
    """
    if isinstance(message, Warning):
        display_warning(message, console=console)
    elif isinstance(message, Message):
        display_message(message, console=console)

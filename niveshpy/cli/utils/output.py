"""Utility functions for styling CLI output."""

import decimal
from collections.abc import (
    Callable,
    Iterable,
    Mapping,
    MutableMapping,
    Sequence,
)
from datetime import date, datetime
from io import StringIO
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, RootModel
from rich import box
from rich.console import Console
from rich.table import Table

from niveshpy.cli.utils.display import (
    capture_for_pager as _capture_for_pager,
)
from niveshpy.cli.utils.display import (
    display as _display,
)
from niveshpy.cli.utils.display import (
    display_error as _display_error,
)
from niveshpy.cli.utils.display import (
    display_json as _display_json,
)
from niveshpy.cli.utils.display import (
    display_warning as _display_warning,
)
from niveshpy.cli.utils.output_models import OutputFormat, SectionBreak, TotalRow
from niveshpy.cli.utils.setup import _console, _error_console
from niveshpy.core.logging import logger
from niveshpy.exceptions import NiveshPyError
from niveshpy.models.output import (
    BaseMessage,
    Message,
    ProgressUpdate,
    Warning,
    format_datetime,
    format_decimal,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo
    from rich import progress

    from niveshpy.cli.utils.output_models import Column


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
    items: Sequence[BaseModel | SectionBreak | TotalRow], schema: dict[str, FieldInfo]
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
            max_width=extras.get("max_width"),
            no_wrap=extras.get("no_wrap", False),
        )

    def mapper(data: object, fmt: Callable[[Any], str] | None) -> str:
        if callable(fmt):
            return fmt(data)
        if data is None:
            return ""
        elif isinstance(data, datetime):
            return format_datetime(data)
        elif isinstance(data, date):
            return data.strftime("%d %b %Y")
        elif isinstance(data, decimal.Decimal):
            return format_decimal(data)
        else:
            return str(data)

    for i, item in enumerate(items):
        if isinstance(item, SectionBreak):
            table.add_section()
        elif isinstance(item, TotalRow):
            if i == len(items) - 1:
                table.show_footer = True
                table.columns[0].footer = item.description
                table.columns[-1].footer = mapper(item.total, None)
                table.footer_style = "bold"
            else:
                table.add_row(
                    item.description,
                    *([None] * (len(ordered_fields) - 2)),
                    mapper(item.total, None),
                    style="bold",
                )
        else:
            row = []
            for field_name in ordered_fields:
                fmt = None
                extras: dict = schema[field_name].json_schema_extra or {}  # type: ignore
                fmt = (
                    extras.get("formatter")
                    if callable(extras.get("formatter"))
                    else None
                )
                value = getattr(item, field_name)
                row.append(mapper(value, fmt))
            table.add_row(*row)

    return table


T = TypeVar("T", bound=BaseModel)


def build_table(
    items: Iterable[Any | SectionBreak | TotalRow],
    columns: Sequence[Column],
) -> Table:
    """Build a Rich Table from an iterable of items with section breaks and total rows."""
    table = Table(header_style="dim", box=box.SIMPLE)
    for column in columns:
        table.add_column(
            column.name,
            justify=column.justify,
            style=column.style,
        )

    for item in items:
        if isinstance(item, SectionBreak):
            table.add_section()
        elif isinstance(item, TotalRow):
            table.add_row(
                item.description,
                *([None] * (len(columns) - 2)),
                str(item.total),
                style="bold",
            )
        else:
            row = []
            for column in columns:
                value = getattr(item, column.key, None)
                row.append(column.format(value))
            table.add_row(*row)

    return table


def build_csv(items: Iterable[Mapping[str, Any]], *, fields: Sequence[str]) -> str:
    """Build a CSV string from an iterable of items."""
    import csv

    f = StringIO()
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(items)
    return f.getvalue()


def display_list(
    cls: type[T],
    items: Sequence[T | SectionBreak | TotalRow],
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

    data_items = [
        item for item in items if not isinstance(item, SectionBreak | TotalRow)
    ]

    root_model = RootModel[Sequence[T]](data_items)
    if fmt == OutputFormat.JSON:
        formatted_data = root_model.model_dump_json(indent=4)
    elif fmt == OutputFormat.CSV:
        import csv

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
        with _capture_for_pager():
            if extra_message:
                _display(extra_message)
            if fmt == OutputFormat.JSON:
                _display_json(str(formatted_data))
            else:
                _display(formatted_data)
    else:
        if fmt == OutputFormat.JSON:
            _display_json(str(formatted_data))
        else:
            _console.print(formatted_data, soft_wrap=True)


def get_progress_bar() -> progress.Progress:
    """Create and return a Rich Progress bar instance for displaying progress."""
    from rich import progress

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
    _display_error(error.message)


def handle_niveshpy_message(
    message: BaseMessage, console: Console | None = None
) -> None:
    """Handle and display NiveshPy messages in the CLI.

    Args:
        message (BaseMessage): The message to handle.
        console (Console | None): Optional Rich Console to use for output.
    """
    if isinstance(message, Warning):
        _display_warning(message, console=console)
    elif isinstance(message, Message):
        _display(message, console=console)

"""Utility functions for styling CLI output."""

from __future__ import annotations

from collections.abc import (
    MutableMapping,
)
from typing import TYPE_CHECKING

from rich.console import Console

from niveshpy.cli.utils.display import display, display_error, display_warning
from niveshpy.cli.utils.setup import _error_console
from niveshpy.core.logging import logger
from niveshpy.exceptions import NiveshPyError
from niveshpy.models.output import BaseMessage, Message, ProgressUpdate, Warning

if TYPE_CHECKING:
    from rich import progress


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
        display(message, console=console)

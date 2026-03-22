"""Models for output formatting and display."""

import datetime
import decimal
import functools
from dataclasses import dataclass


@dataclass
class Message:
    """Model for a general message."""

    content: str
    """The content of the message."""

    def __rich__(self) -> str:
        """Get rich formatted content."""
        return self.content


@dataclass
class Warning:
    """Model for a warning message.

    Use this to indicate non-critical issues that the user should be aware of
    but that does not prevent normal operation of the current process.
    """

    content: str
    """The content of the warning message."""

    def __rich__(self) -> str:
        """Get rich formatted content."""
        return self.content


@dataclass
class ProgressUpdate:
    """Model for progress update information."""

    stage: str
    """Unique name of the current stage."""

    description: str
    """A user-friendly description of the stage."""

    current: int | None
    """The current progress value. None if unknown."""

    total: int | None
    """The total value for completion. None if unknown."""


BaseMessage = Message | Warning | ProgressUpdate
"""Union type for all output message models."""


def format_decimal(
    value: decimal.Decimal | None,
    is_percentage: bool = False,
    ignore_negative: bool = False,
) -> str:
    """Format decimal value as a string with appropriate formatting."""
    value_str = ""
    if value is None:
        return "N/A"
    if is_percentage:
        value_str = f"{value:.2%}"
    else:
        value_str = f"{value:,}"
    if not ignore_negative and value < 0:
        value_str = f"[red]{value_str}"
    return value_str


format_percentage = functools.partial(format_decimal, is_percentage=True)


def format_datetime(dt: datetime.datetime) -> str:
    """Format a datetime object to a relative time string.

    If the datetime is within 7 days, it shows relative time (e.g., "about 3 hours ago").
    If older than 7 days, it shows the absolute date (e.g., "on Jan 01, 2023").

    Args:
        dt (datetime.datetime): The datetime object to format.

    Returns:
        str: A human-readable relative time string.

    """
    now = datetime.datetime.now()
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

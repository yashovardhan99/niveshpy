"""Models for output formatting and display."""

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

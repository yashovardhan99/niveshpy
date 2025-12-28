"""Models for output formatting and display."""

from dataclasses import dataclass


class BaseMessage:
    """Base model for messages."""


@dataclass
class Message(BaseMessage):
    """Model for a general message."""

    content: str
    """The content of the message."""

    def __rich__(self) -> str:
        """Get rich formatted content."""
        return self.content


@dataclass
class Warning(BaseMessage):
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
class ProgressUpdate(BaseMessage):
    """Model for progress update information."""

    stage: str
    """Unique name of the current stage."""

    description: str
    """A user-friendly description of the stage."""

    current: int | None
    """The current progress value. None if unknown."""

    total: int | None
    """The total value for completion. None if unknown."""

"""Lightweight output models for CLI output formatting."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any, Generic, Literal, TypeVar


class OutputFormat(StrEnum):
    """Enumeration of supported output formats."""

    TABLE = auto()
    CSV = auto()
    JSON = auto()


class SectionBreak:
    """Marker class for section breaks in output."""


TotalType = TypeVar("TotalType")


@dataclass
class TotalRow(Generic[TotalType]):
    """Marker class for total rows in output."""

    total: TotalType
    description: str = "Total"


@dataclass(slots=True, frozen=True)
class Column:
    """Class for specifying column metadata for tabular output.

    Attributes:
        key (str): The key corresponding to the data field for this column.
        name (str): The display name of the column header. Defaults to a title-cased version of the key.
        style (str): Optional Rich style string for styling the column.
        formatter (Callable[[Any], str]): A function to format the cell value for display. Defaults to str.
        justify (Literal["default", "left", "center", "right", "full"]): Text justification for the column. Defaults to "left".
    """

    key: str
    name: str = ""
    style: str = ""
    getter: Callable[[Any], Any] | None = None
    formatter: Callable[[Any], str] = str
    justify: Literal["default", "left", "center", "right", "full"] = "left"

    def __post_init__(self):
        """Set default name to key if not provided."""
        if not self.name:
            object.__setattr__(self, "name", self.key.replace("_", " ").title())

    def format(self, value: Any) -> str:
        """Format a value using the specified formatter.

        Args:
            value (Any): The value to format.

        Returns:
            str: The formatted string representation of the value.
        """
        return self.formatter(value)

    def get(self, obj: Any) -> Any:
        """Get the value for this column from an object using the getter or key.

        Args:
            obj (Any): The object to get the value from.

        Returns:
            Any: The value obtained from the object.
        """
        if self.getter is not None:
            return self.getter(obj)
        return getattr(obj, self.key, None)

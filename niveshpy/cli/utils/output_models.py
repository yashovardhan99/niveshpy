"""Lightweight output models for CLI output formatting."""

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Generic, TypeVar


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

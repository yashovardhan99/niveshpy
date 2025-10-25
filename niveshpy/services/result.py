"""Holders for service results."""

from typing import Generic, TypeVar
from dataclasses import dataclass
from enum import StrEnum, auto


T = TypeVar("T")


@dataclass
class ListResult(Generic[T]):
    """Class representing a list result with total count and results."""

    data: T
    total: int


class MergeAction(StrEnum):
    """Enum for merge actions."""

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    NOTHING = "NOTHING"


@dataclass
class InsertResult(Generic[T]):
    """Class representing the result of an insert operation."""

    action: MergeAction
    data: T


class ResolutionStatus(StrEnum):
    """Enum for resolution status."""

    EXACT = auto()
    AMBIGUOUS = auto()
    NOT_FOUND = auto()


@dataclass(frozen=True)
class SearchResolution(Generic[T]):
    """Class representing the resolution of a search request."""

    status: ResolutionStatus
    exact: T | None = None
    candidates: list[T] | None = None
    queries: tuple[str, ...] = ()

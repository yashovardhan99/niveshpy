"""Holders for service results."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

T = TypeVar("T")


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

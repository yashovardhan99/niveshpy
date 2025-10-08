"""Database query utilities."""

from dataclasses import dataclass
from enum import StrEnum, auto


class ResultFormat(StrEnum):
    """Result format options."""

    POLARS = auto()
    SINGLE = auto()
    LIST = auto()


@dataclass
class QueryOptions:
    """Options for querying the database."""

    text_query: str | None = None
    limit: int | None = None
    offset: int | None = None


DEFAULT_QUERY_OPTIONS = QueryOptions()

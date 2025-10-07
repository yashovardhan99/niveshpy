"""Database query utilities."""

from dataclasses import dataclass


@dataclass
class QueryOptions:
    """Options for querying the database."""

    text_query: str | None = None
    limit: int | None = None
    offset: int | None = None


DEFAULT_QUERY_OPTIONS = QueryOptions()

"""SQLite converters module."""

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import cattrs
from cattrs.cols import (
    is_mapping,
    mapping_structure_factory,
    mapping_unstructure_factory,
)

_db_converter = cattrs.Converter()


@_db_converter.register_unstructure_hook
def _unstructure_date(value: date) -> str:
    """Unstructure a date to an ISO format string."""
    return date.isoformat(value)


@_db_converter.register_structure_hook
def _structure_date(value: str, cls: type[date]) -> date:
    """Structure an ISO format string back to a date."""
    return date.fromisoformat(value)


@_db_converter.register_unstructure_hook
def _unstructure_datetime(value: datetime) -> str:
    """Unstructure a datetime to an ISO format string.

    Converts timezone-aware datetimes to UTC naive datetimes before unstructuring.
    """
    return value.astimezone(UTC).replace(tzinfo=None).isoformat()


@_db_converter.register_structure_hook
def _structure_datetime(value: str, cls: type[datetime]) -> datetime:
    """Structure an ISO format string back to a datetime.

    Assumes the stored datetime is in UTC and returns a timezone-naive datetime.
    """
    return (
        datetime.fromisoformat(value)
        .replace(tzinfo=UTC)
        .astimezone()
        .replace(tzinfo=None)
    )


@_db_converter.register_unstructure_hook
def _unstructure_decimal(value: Decimal) -> str:
    """Unstructure a Decimal to a string."""
    return str(value)


@_db_converter.register_structure_hook
def _structure_decimal(value: str | float | int, cls: type[Decimal]) -> Decimal:
    """Structure a string back to a Decimal."""
    return Decimal(str(value))


@_db_converter.register_structure_hook_factory(is_mapping)
def _make_structure_mapping_hook(type: Any, converter: cattrs.Converter):
    base_hook = mapping_structure_factory(type, converter)

    def hook(data, type):
        return base_hook(json.loads(data) if isinstance(data, str) else data, type)

    return hook


@_db_converter.register_unstructure_hook_factory(is_mapping)
def _make_unstructure_mapping_hook(cl: Any, converter: cattrs.Converter):
    base_hook = mapping_unstructure_factory(dict, converter)

    def hook(data: Mapping) -> str:
        return json.dumps(base_hook(data))

    return hook


def get_converter() -> cattrs.Converter:
    """Get the Cattrs converter instance for SQLite."""
    return _db_converter

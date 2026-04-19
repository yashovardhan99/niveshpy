"""Cattrs converter for NiveshPy domain types."""

import datetime

import cattrs

_converter = cattrs.Converter()


@_converter.register_unstructure_hook
def _unstructure_datetime(dt: datetime.datetime) -> str:
    """Unstructure datetime objects to ISO format strings."""
    return dt.isoformat()


@_converter.register_structure_hook
def _structure_datetime(dt_str: str, cls: type[datetime.datetime]) -> datetime.datetime:
    """Structure ISO format strings back to datetime objects."""
    return datetime.datetime.fromisoformat(dt_str)


def get_converter() -> cattrs.Converter:
    """Get the Cattrs converter instance for NiveshPy domain types."""
    return _converter

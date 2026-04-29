"""Cattrs converter for NiveshPy domain types."""

import datetime
from decimal import Decimal
from enum import StrEnum

import cattrs
from cattrs.gen import make_dict_unstructure_fn, override

from niveshpy.models.account import AccountPublic
from niveshpy.models.security import SecurityPublic

_json_converter = cattrs.Converter()
_csv_converter = cattrs.Converter()


@_csv_converter.register_unstructure_hook
@_json_converter.register_unstructure_hook
def _unstructure_datetime(dt: datetime.datetime) -> str:
    """Unstructure datetime objects to ISO format strings."""
    return dt.isoformat()


@_csv_converter.register_unstructure_hook
@_json_converter.register_unstructure_hook
def _unstructure_date(dt: datetime.date) -> str:
    """Unstructure date objects to ISO format strings."""
    return dt.isoformat()


@_json_converter.register_unstructure_hook
def _unstructure_decimal_json(dec: Decimal) -> str:
    """Unstructure Decimal objects to strings."""
    return str(dec)


@_csv_converter.register_unstructure_hook
@_json_converter.register_unstructure_hook
def _unstructure_str_enum(enum_val: StrEnum) -> str:
    """Unstructure string-based Enum values to their string representation."""
    return enum_val.value


_json_converter.register_unstructure_hook(
    AccountPublic,
    make_dict_unstructure_fn(
        AccountPublic, _json_converter, created_at=override(rename="created")
    ),
)

_csv_converter.register_unstructure_hook(
    AccountPublic,
    make_dict_unstructure_fn(
        AccountPublic,
        _csv_converter,
        source=override(omit=False),
        created_at=override(rename="created"),
        properties=override(omit=True),
    ),
)

_csv_converter.register_unstructure_hook(
    SecurityPublic,
    make_dict_unstructure_fn(
        SecurityPublic,
        _csv_converter,
        source=override(omit=False),
        properties=override(omit=True),
    ),
)


def get_json_converter() -> cattrs.Converter:
    """Get the Cattrs converter instance for JSON."""
    return _json_converter


def get_csv_converter() -> cattrs.Converter:
    """Get the Cattrs converter instance for CSV."""
    return _csv_converter

"""Cattrs converter for NiveshPy domain types."""

import datetime
from decimal import Decimal
from enum import StrEnum

import cattrs
from cattr.preconf.json import make_converter as make_json_converter
from cattrs.gen import make_dict_unstructure_fn, override

from niveshpy.models.account import AccountPublic
from niveshpy.models.price import PricePublic
from niveshpy.models.report import Allocation, Holding, PerformanceHolding
from niveshpy.models.security import SecurityPublic
from niveshpy.models.transaction import TransactionPublic

_json_converter = make_json_converter()
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


_csv_converter.register_unstructure_hook(
    AccountPublic,
    make_dict_unstructure_fn(
        AccountPublic,
        _csv_converter,
        source=override(omit=False),
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

_csv_converter.register_unstructure_hook(
    PricePublic,
    make_dict_unstructure_fn(
        PricePublic,
        _csv_converter,
        source=override(omit=False),
        properties=override(omit=True),
        security=override(omit=True),
        security_key=override(rename="security"),
    ),
)

_json_converter.register_unstructure_hook(
    PricePublic,
    make_dict_unstructure_fn(
        PricePublic,
        _json_converter,
        security_key=override(omit=True),
    ),
)

_csv_converter.register_unstructure_hook(
    TransactionPublic,
    make_dict_unstructure_fn(
        TransactionPublic,
        _csv_converter,
        source=override(omit=False),
        properties=override(omit=True),
        security=override(omit=True),
        account=override(omit=True),
        security_key=override(rename="security"),
        account_id=override(rename="account"),
        cost=override(omit_if_default=True),
    ),
)

_json_converter.register_unstructure_hook(
    TransactionPublic,
    make_dict_unstructure_fn(
        TransactionPublic,
        _json_converter,
        security_key=override(omit=True),
        account_id=override(omit=True),
        cost=override(omit_if_default=True),
    ),
)

_json_converter.register_unstructure_hook(
    Holding,
    make_dict_unstructure_fn(
        Holding, _json_converter, amount=override(rename="current")
    ),
)

_csv_converter.register_unstructure_hook(
    Holding,
    make_dict_unstructure_fn(
        Holding,
        _csv_converter,
        amount=override(rename="current"),
        account=override(omit=True),
        security=override(omit=True),
        account_id=override(rename="account", omit=False),
        security_key=override(rename="security", omit=False),
    ),
)

_json_converter.register_unstructure_hook(
    Allocation,
    make_dict_unstructure_fn(
        Allocation,
        _json_converter,
        security_category=override(omit_if_default=True),
        security_type=override(omit_if_default=True),
    ),
)

_csv_converter.register_unstructure_hook(
    Allocation,
    make_dict_unstructure_fn(
        Allocation,
        _csv_converter,
        security_category=override(omit_if_default=True),
        security_type=override(omit_if_default=True),
    ),
)

_json_converter.register_unstructure_hook(
    PerformanceHolding,
    make_dict_unstructure_fn(
        PerformanceHolding,
        _json_converter,
        _cattrs_include_init_false=True,
        account_id=override(omit=True),
        security_key=override(omit=True),
    ),
)

_csv_converter.register_unstructure_hook(
    PerformanceHolding,
    make_dict_unstructure_fn(
        PerformanceHolding,
        _csv_converter,
        _cattrs_include_init_false=True,
        account=override(omit=True),
        security=override(omit=True),
        account_id=override(rename="account"),
        security_key=override(rename="security"),
    ),
)


def get_json_converter() -> cattrs.Converter:
    """Get the Cattrs converter instance for JSON."""
    return _json_converter


def get_csv_converter() -> cattrs.Converter:
    """Get the Cattrs converter instance for CSV."""
    return _csv_converter

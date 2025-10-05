"""Type aliases for NiveshPy models.

This module is designed to work with static type checkers and as such
imports optional dependencies like pandas. Avoid importing this module
directly, instead import this module inside a `if TYPE_CHECKING` block.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

import pandas as pd
import polars as pl

from niveshpy.models.base import OHLC, Quote, SourceConfig, SourceInfo, Ticker

# Type Aliases
PolarsFrameType = pl.DataFrame | pl.LazyFrame

NiveshPyType = Ticker | Quote | OHLC | SourceInfo | SourceConfig

QuotesIterable = Iterable[Quote] | Iterable[OHLC] | PolarsFrameType
TickersIterable = Iterable[Ticker] | PolarsFrameType

NiveshPyIterable = PolarsFrameType | Iterable[NiveshPyType]

NiveshPyOutputType = dict[str, list] | pl.DataFrame | pl.LazyFrame | pd.DataFrame | str

# Type Variables
PolarsFrame = TypeVar("PolarsFrame", pl.DataFrame, pl.LazyFrame)

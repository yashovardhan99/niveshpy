"""Base models for NiveshPy."""

from datetime import date, timedelta
from decimal import Decimal
from enum import Flag, auto
from typing import NamedTuple

import polars as pl


class Ticker(NamedTuple):
    """Class to hold ticker information."""

    symbol: str
    name: str
    isin: str | None

    @classmethod
    def get_polars_schema(cls) -> pl.Schema:
        """Get the Polars schema for the Ticker class."""
        return pl.Schema(
            {
                "symbol": pl.String(),
                "name": pl.String(),
                "isin": pl.String(),
            }
        )


class OHLC(NamedTuple):
    """Class to hold OHLC data."""

    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    @classmethod
    def get_polars_schema(cls) -> pl.Schema:
        """Get the Polars schema for the OHLC class."""
        return pl.Schema(
            {
                "symbol": pl.String(),
                "date": pl.Date(),
                "open": pl.Decimal(scale=4),
                "high": pl.Decimal(scale=4),
                "low": pl.Decimal(scale=4),
                "close": pl.Decimal(scale=4),
            }
        )


class Quote(NamedTuple):
    """Class to hold price data."""

    symbol: str
    date: date
    price: Decimal

    @classmethod
    def get_polars_schema(cls) -> pl.Schema:
        """Get the Polars schema for the Quote class."""
        return pl.Schema(
            {
                "symbol": pl.String(),
                "date": pl.Date(),
                "price": pl.Decimal(scale=4),
            }
        )


class SourceInfo(NamedTuple):
    """Class to hold source information."""

    name: str
    description: str
    key: str
    version: int
    """This will later add support for source migrations."""


class SourceStrategy(Flag):
    """Enum for source strategies.

    This enum defines the different strategies for data sources.
    Strategies can be combined using bitwise OR.
    These help in determining how to fetch and store data from the source.
    For example, if the source only supports fetching data for all tickers at a time,
    NiveshPy will store the data and use them in the future automatically.
    """

    DEFAULT = 0
    """Use this when the source does not require any special strategy.
    
    Default strategy:
    - The source only fetches data for the provided tickers (or all tickers if none are provided).
    - The source returns OHLC data.
    """

    ALL_TICKERS = auto()
    """The source fetches data for all tickers at once.
    Used for sources that do not support fetching data only for a list of provided tickers.
    """

    SINGLE_QUOTE = auto()
    """The source returns a single quote for the provided ticker.
    Used for sources that do not support fetching OHLC data.
    """


class SourceConfig(NamedTuple):
    """Class to hold source configuration."""

    ticker_refresh_interval: timedelta | None = None
    """The time interval at which the source can be checked for new tickers.
    
    If this value is None, the source will not be checked for new tickers.
    Default is None."""
    data_refresh_interval: timedelta = timedelta(days=1)
    """The time interval at which the source can be checked for new data.
    
    Note that this only applies to new data. Historical data, once fetched,
    will not be fetched again.
    
    This frequency will be ticker-specific unless the source uses the `ALL_TICKERS` strategy,
    in which case it will be source-specific."""
    data_group_period: timedelta | None = None
    """The time period for which data can be grouped at source.
    
    This is used to limit the amount of calls made to the source.
    For example, if the source can return data for 1 month at a time,
    this should be set to 30 days.

    If this value is None, the data will not be grouped.
    
    This value will be passed to `polars.DataFrame.group_by_dynamic`
    to group the data by the specified time period.

    Default is None.
    """
    source_strategy: SourceStrategy = SourceStrategy.DEFAULT
    """The strategy to use for the source. Multiple strategies can be combined using bitwise OR.
    This is used to determine how to fetch and store data from the source."""

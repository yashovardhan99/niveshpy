"""Utility functions for niveshpy."""

from __future__ import annotations

import logging
from datetime import date
from multiprocessing import Lock
from pathlib import Path
from typing import TYPE_CHECKING

import platformdirs
import polars as pl

from niveshpy.models import (
    ReturnFormat,
)

if TYPE_CHECKING:
    from niveshpy.models.types import (
        NiveshPyIterable,
        NiveshPyOutputType,
        PolarsFrame,
        PolarsFrameType,
    )


logger = logging.getLogger(__name__)


def get_tickers_dir() -> Path:
    """Get the directory for tickers."""
    return platformdirs.user_data_path("niveshpy").joinpath("tickers")


def get_quotes_dir() -> Path:
    """Get the directory for quotes."""
    return platformdirs.user_data_path("niveshpy").joinpath("quotes")


def handle_input(
    data: NiveshPyIterable,
    schema: pl.Schema | None = None,
) -> pl.LazyFrame:
    """Handle input data and convert it to a Polars LazyFrame."""
    if isinstance(data, pl.DataFrame | pl.LazyFrame):
        return data.lazy()
    else:
        return pl.from_dicts(map(lambda x: x._asdict(), data), schema=schema).lazy()


def format_output(
    data: PolarsFrameType,
    format: ReturnFormat | str,
) -> NiveshPyOutputType:
    """Format the output based on the specified format."""
    data = data.lazy()
    if isinstance(format, str):
        format = ReturnFormat(format)

    if format == ReturnFormat.DICT:
        return data.collect().to_dict(as_series=False)
    elif format == ReturnFormat.PL_DATAFRAME:
        return data.collect()
    elif format == ReturnFormat.PL_LAZYFRAME:
        return data
    elif format == ReturnFormat.PD_DATAFRAME:
        return data.collect().to_pandas()
    elif format == ReturnFormat.JSON:
        return data.collect().write_json()
    elif format == ReturnFormat.CSV:
        return data.collect().write_csv()
    else:
        raise ValueError(f"Unsupported format: {format}")


def apply_filters(
    frame: PolarsFrame,
    source_keys: list[str] | None,
    filters: dict[str, list[str]] | None,
    schema: pl.Schema | None = None,
) -> PolarsFrame:
    """Filter records based on source keys and other filters.

    All filters are combined using OR. The keys of the dictionary are
    the column names and the values are lists of values to filter by.

    Examples:
    >>>     filters = {
    ...         "symbol": ["0500209", "500210"],
    ...         "name": ["UTI Nifty Next 50 Index Fund - Direct"]
    ...     }

    This will return only the records that match the specified symbol or name.
    If filters is None, all records are returned.
    """
    if source_keys:
        frame = frame.filter(pl.col("source_key").is_in(source_keys))
    if filters:
        columns = schema.names() if schema else frame.collect_schema().names()
        expressions = None
        for column, values in filters.items():
            if column in columns:
                if expressions is None:
                    expressions = pl.lit(False)
                expressions = expressions | pl.col(column).is_in(values)
        if expressions is not None:
            frame = frame.filter(expressions)
    return frame


def save_tickers(tickers: PolarsFrameType) -> None:
    """Save tickers to a parquet file partitioned by source_key."""
    file_path = get_tickers_dir().joinpath("tickers.parquet")
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
    tickers.lazy().collect().write_parquet(file_path)


def load_tickers() -> pl.LazyFrame:
    """Load tickers from a parquet file."""
    file_path = get_tickers_dir().joinpath("tickers.parquet")
    if not file_path.exists():
        raise FileNotFoundError(f"File {file_path} does not exist.")
    return pl.scan_parquet(file_path)


_availability_schema = pl.Schema(
    {
        "source_key": pl.Utf8,
        "date": pl.Date,
    }
)

_availability_lock = Lock()


def mark_quotes_as_available(
    source_key: str,
    start_date: date,
    end_date: date,
) -> None:
    """Mark quotes as available for a given source key and date range.

    This is only applicable for sources with ALL_TICKERS strategy.
    """
    logger.debug(
        f"Marking quotes as available for source_key={source_key}, "
        f"start_date={start_date}, end_date={end_date}"
    )
    file_path = get_quotes_dir().joinpath("availability.parquet")
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)

    # Use a lock to ensure thread safety when writing to the file
    with _availability_lock:
        if file_path.exists():
            df_availability = pl.read_parquet(file_path)
        else:
            df_availability = _availability_schema.to_frame(eager=True)

        df_new_availability = (
            pl.date_range(start=start_date, end=end_date, interval="1d", eager=True)
            .to_frame("date")
            .with_columns(pl.lit(source_key).alias("source_key"))
        )

        df_availability = df_availability.update(
            df_new_availability,
            on=["source_key", "date"],
            how="full",
        )
        df_availability.write_parquet(file_path)


def check_quotes_availability(
    source_key: str,
    start_date: date,
    end_date: date,
) -> pl.Series:
    """Check if quotes are available for a given source key and date range.

    This is only applicable for sources with ALL_TICKERS strategy.
    """
    file_path = get_quotes_dir().joinpath("availability.parquet")
    if not file_path.exists():
        return _availability_schema.to_frame(eager=True).select("date").to_series()

    df_availability = pl.read_parquet(file_path)
    df_availability = df_availability.filter(
        (pl.col("source_key") == source_key)
        & (pl.col("date").is_between(start_date, end_date))
    )
    return df_availability.select("date").to_series()


def save_quotes(quotes: pl.DataFrame, source_key: str) -> None:
    """Save quotes to a parquet file."""
    file_path = get_quotes_dir().joinpath(f"quotes_{source_key}.parquet")
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
    quotes.write_parquet(file_path)


def load_quotes(source_key: str, schema: pl.Schema) -> pl.LazyFrame:
    """Load quotes from a parquet file."""
    file_path = get_quotes_dir().joinpath(f"quotes_{source_key}.parquet")
    if not file_path.exists():
        logger.info(f"File {file_path} does not exist.")
        return schema.to_frame(eager=False)
    return pl.scan_parquet(file_path, schema=schema)

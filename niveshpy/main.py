"""Mutual Fund utilities for Python."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, datetime, timedelta
import logging
import importlib
import pkgutil
import warnings

from niveshpy.models.helpers import ReturnFormat
from niveshpy.models.sources import Source
from niveshpy.models.base import OHLC, Quote, SourceInfo, SourceStrategy, Ticker
import niveshpy.plugins as _local_plugins
from niveshpy.models.plugins import Plugin
from niveshpy.utils import (
    check_quotes_availability,
    format_output,
    apply_filters,
    handle_input,
    load_quotes,
    load_tickers,
    mark_quotes_as_available,
    save_quotes,
    save_tickers,
)

from typing import TYPE_CHECKING, Literal, overload
from collections.abc import Collection
from collections.abc import Iterable

import polars as pl


if TYPE_CHECKING:
    import pandas as pd
    from niveshpy.models.types import NiveshPyOutputType, QuotesIterable

logger = logging.getLogger(__name__)


def _import_plugin(name: str) -> Plugin | None:
    """Import a plugin by name."""
    try:
        module = importlib.import_module(name)
        if hasattr(module, "register_plugin"):
            plugin = module.register_plugin()
            if isinstance(plugin, Plugin):
                return plugin
            else:
                logger.warning(f"Plugin {name} does not inherit from Plugin class")
        else:
            logger.warning(f"Plugin {name} does not have register_plugin() method")
    except ImportError:
        logger.exception(f"Failed to import plugin {name}")
    return None


def _import_local_plugins() -> Iterable[Plugin]:
    """Import all local plugins."""
    return filter(
        None,
        (
            _import_plugin(name)
            for _, name, ispkg in pkgutil.iter_modules(
                _local_plugins.__path__, "niveshpy.plugins."
            )
            if not ispkg
        ),
    )


class Nivesh:
    """This is the base class for NiveshPy."""

    def __init__(self) -> None:
        """Initialize the Nivesh class."""
        logger.debug("Initializing Nivesh")
        local_plugins = _import_local_plugins()
        self.plugins: list[Plugin] = []
        for plugin in local_plugins:
            logger.debug(f"Loaded plugin: {plugin.get_info()}")
            self.plugins.append(plugin)
        logger.debug(f"Loaded {len(self.plugins)} plugins")
        logger.debug("Nivesh initialized")

    def register_plugin(self, plugin: Plugin):
        """Register a custom plugin."""
        if isinstance(plugin, Plugin):
            self.plugins.append(plugin)
            logger.info(f"Registered plugin: {plugin.get_info()}")
        else:
            raise TypeError("Plugin must be an instance of Plugin class")

    def _get_sources(self, source_keys: list[str] | None = None) -> Iterable[Source]:
        """Get the list of sources from all plugins."""
        logger.debug("Getting sources from all plugins")
        for plugin in self.plugins:
            for source in plugin.get_sources():
                if source_keys is None or source.get_source_key() in source_keys:
                    yield source
                    logger.debug(f"Loaded source: {source.get_source_info()}")

    def get_sources(self, source_keys: list[str] | None = None) -> Iterable[SourceInfo]:
        """Get the list of sources from all plugins.

        Args:
            source_keys (List[str] | None): The source keys to filter by.
                Defaults to None.
                The source key is the key used to identify the source of the tickers.
                If source_keys is specified, only the sources from the specified keys
                are returned.
                For example, to filter by source key, you can use:
                source_key = ["amfi"]
                This will return only the sources from the AMFI source.
                If source_key is None, all sources from all plugins are returned.

        Returns:
            Iterable[SourceInfo]: An iterable of SourceInfo objects.
        """
        sources = self._get_sources(source_keys)
        return map(lambda source: source.get_source_info(), sources)

    @overload
    def get_tickers(
        self,
        filters: dict[str, list[str]] | None = None,
        source_keys: list[str] | None = None,
        format: Literal[ReturnFormat.DICT] = ...,
    ) -> dict[str, list]: ...

    @overload
    def get_tickers(
        self,
        filters: dict[str, list[str]] | None = None,
        source_keys: list[str] | None = None,
        format: Literal[ReturnFormat.PL_DATAFRAME] = ...,
    ) -> pl.DataFrame: ...

    @overload
    def get_tickers(
        self,
        filters: dict[str, list[str]] | None = None,
        source_keys: list[str] | None = None,
        format: Literal[ReturnFormat.PL_LAZYFRAME] = ...,
    ) -> pl.LazyFrame: ...

    @overload
    def get_tickers(
        self,
        filters: dict[str, list[str]] | None = None,
        source_keys: list[str] | None = None,
        format: Literal[ReturnFormat.PD_DATAFRAME] = ...,
    ) -> pd.DataFrame: ...

    @overload
    def get_tickers(
        self,
        filters: dict[str, list[str]] | None = None,
        source_keys: list[str] | None = None,
        format: Literal[ReturnFormat.JSON, ReturnFormat.CSV] = ...,
    ) -> str: ...

    def get_tickers(
        self,
        filters: dict[str, list[str]] | None = None,
        source_keys: list[str] | None = None,
        format: ReturnFormat | str = ReturnFormat.DICT,
    ) -> NiveshPyOutputType:
        """Get the list of tickers from all plugins.

        Args:
            filters (Dict[str, List[str]] | None): Filters to apply to the tickers.
                Defaults to None.
                See [niveshpy.utils.filter_tickers] for available filters.

            source_keys (List[str] | None): The source keys to filter by.
                Defaults to None. If source_keys is specified, only the tickers
                from the specified sources are returned.
                If source_key is None, all tickers from all sources are returned.

            format (ReturnFormat): The format of the returned tickers.
                Defaults to ReturnFormat.DICT. See [niveshpy.models.helpers.ReturnFormat] for available formats.

        Returns:
            NiveshPyOutputType: The list of tickers in the specified format.
            The returned data has the following columns:
                - symbol: The ticker symbol.
                - name: The name of the ticker.
                - isin: The ISIN of the ticker.
                - source_key: The source key of the ticker.
                - last_updated: The last updated date of the source.
        """
        df_tickers = (
            Ticker.get_polars_schema()
            .to_frame(eager=False)
            .with_columns(
                pl.lit(None).cast(pl.String()).alias("source_key"),
            )
        )
        pre_loaded_sources: dict[str, datetime] = {}
        try:
            logger.debug("Getting locally saved tickers")
            df_tickers_pre = load_tickers()
            logger.debug("Loaded locally saved tickers")
            df_sources = (
                df_tickers_pre.group_by("source_key")
                .agg(pl.min("last_updated").alias("last_updated"))
                .collect()
            )
            for row in df_sources.iter_rows(named=True):
                source_key = row["source_key"]
                last_updated = row["last_updated"]
                pre_loaded_sources[source_key] = last_updated
        except FileNotFoundError:
            logger.debug("No locally saved tickers found")
            df_tickers_pre = df_tickers.clone().with_columns(
                pl.lit(None).cast(pl.Datetime()).alias("last_updated"),
            )

        logger.debug("Getting tickers from all plugins")
        all_tickers = [df_tickers]
        for source in self._get_sources(source_keys):
            # This will run for all sources matching the source_keys (if applicable)
            key = source.get_source_key()
            refresh_interval = source.get_source_config().ticker_refresh_interval
            if key in pre_loaded_sources and (
                refresh_interval is None
                or (datetime.now() - pre_loaded_sources[key]) < refresh_interval
            ):
                logger.debug(f"Skipping source {key} as it is up to date")
            else:
                logger.debug(f"Getting tickers from source {key}")
                all_tickers.append(
                    handle_input(
                        source.get_tickers(), Ticker.get_polars_schema()
                    ).with_columns(pl.lit(key).alias("source_key"))
                )

        logger.debug("Combining tickers from all plugins")
        df_tickers = pl.concat(all_tickers, how="vertical_relaxed").select(
            pl.col("symbol").cast(pl.String()),
            pl.col("name").cast(pl.String()),
            pl.col("isin").cast(pl.String()),
            pl.col("source_key").cast(pl.String()),
            pl.lit(datetime.now()).alias("last_updated"),
        )

        df_tickers_collected = df_tickers.collect()
        if df_tickers_collected.height > 0:
            logger.debug("Combining tickers with locally saved tickers")
            df_tickers_collected = df_tickers_pre.collect().update(
                df_tickers_collected,
                on=["source_key", "symbol"],
                how="full",
            )

            logger.debug("Saving all tickers to local file")
            save_tickers(df_tickers_collected)
        else:
            logger.debug("No new tickers found")
            df_tickers_collected = df_tickers_pre.collect()

        logger.debug("Applying filters to tickers")
        df_tickers_collected = apply_filters(df_tickers_collected, source_keys, filters)
        return format_output(df_tickers_collected, format)

    def _handle_tickers(self, *tickers: str | tuple[str, str]) -> pl.DataFrame:
        """Handle the input tickers and return a DataFrame with the requested tickers."""
        tickers_grouped: dict[str | None, list[str]] = defaultdict(list)
        for ticker in tickers:
            if isinstance(ticker, str):
                tickers_grouped[None].append(ticker)
            elif isinstance(ticker, tuple) and len(ticker) == 2:
                tickers_grouped[ticker[1]].append(ticker[0])
            else:
                raise ValueError("Invalid ticker format", ticker)

        df_requested_tickers = pl.concat(
            [
                pl.DataFrame(
                    {
                        "symbol": tickers_grouped[source_key],
                        "source_key": source_key,
                    },
                    schema_overrides={"source_key": pl.Utf8},
                )
                for source_key in tickers_grouped
            ]
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Requested tickers:")
            logger.debug(df_requested_tickers)

        # Find the sources for requested tickers where source_key is None

        df_tickers_matched = self.get_tickers(
            filters=df_requested_tickers.filter(pl.col("source_key").is_null())
            .select("symbol")
            .to_dict(as_series=False),
            format=ReturnFormat.PL_DATAFRAME,
        )

        unknown_tickers = (
            df_requested_tickers.filter(pl.col("source_key").is_null())
            .join(
                df_tickers_matched,
                on="symbol",
                how="anti",
            )
            .select("symbol")
            .to_dict(as_series=False)["symbol"]
        )
        if len(unknown_tickers) > 0:
            warnings.warn(
                f"The following tickers are not found in any known source: {unknown_tickers}",
                stacklevel=3,
            )
        df_requested_tickers = df_requested_tickers.filter(
            pl.col("source_key").is_not_null()
        )
        if df_tickers_matched.height > 0:
            df_requested_tickers = df_requested_tickers.vstack(
                df_tickers_matched.select("symbol", "source_key")
            )

        return df_requested_tickers

    def _get_quotes(
        self,
        symbols: Collection[str],
        source: Source,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        """Helper function to get quotes from a single source."""
        source_strategy = source.get_source_config().source_strategy
        source_key = source.get_source_key()
        schema = (
            Quote.get_polars_schema()
            if SourceStrategy.SINGLE_QUOTE in source_strategy
            else OHLC.get_polars_schema()
        )

        # Get locally saved quotes
        df_quotes = load_quotes(source_key, schema)

        actual_start_date = (
            start_date
            if start_date
            else date.today() - source.get_source_config().data_refresh_interval
        )
        actual_end_date = end_date if end_date else date.today()

        # Create a LazyFrame with the date range
        date_range = pl.date_range(
            start=actual_start_date,
            end=actual_end_date,
        ).alias("date")

        df_date_range = pl.LazyFrame().select(date_range)

        group_period = source.get_source_config().data_group_period

        if SourceStrategy.ALL_TICKERS not in source_strategy:
            df_available = df_quotes.filter(pl.col("symbol").is_in(symbols))
            df_date_range = df_date_range.join(
                pl.LazyFrame(
                    {
                        "symbol": symbols,
                    },
                    schema_overrides={"symbol": pl.Utf8},
                ),
                how="cross",
            )
            df_missing = df_date_range.join(
                df_available,
                on=["symbol", "date"],
                how="anti",
            ).sort("date")

            if group_period:
                df_missing = df_missing.group_by_dynamic(
                    "date",
                    every=group_period,
                    label="datapoint",
                    group_by="symbol",
                ).agg(
                    pl.col("date").first().alias("start_date"),
                    pl.col("date").last().alias("end_date"),
                )
        else:
            df_available = (
                check_quotes_availability(
                    source_key, actual_start_date, actual_end_date
                )
                .to_frame("date")
                .lazy()
            )

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Available quotes:")
                logger.debug(df_available.collect())

            df_missing = df_date_range.join(
                df_available,
                on=["date"],
                how="anti",
            ).sort("date")

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Missing quotes:")
                logger.debug(df_missing.collect())

            if group_period:
                df_missing = df_missing.group_by_dynamic(
                    "date",
                    every=group_period,
                    label="datapoint",
                ).agg(
                    pl.col("date").first().alias("start_date"),
                    pl.col("date").last().alias("end_date"),
                )

        # Get unavailable quotes from the source
        new_quotes = [schema.to_frame(eager=False)]

        data_refresh_threshold = (
            date.today() - source.get_source_config().data_refresh_interval
        )

        with ThreadPoolExecutor() as executor:
            futures: list[tuple[Future[QuotesIterable], date, date]] = []

            for row in df_missing.collect().iter_rows(named=True):
                start = row.get("start_date", row.get("date"))
                end = row.get("end_date", row.get("date"))

                if not isinstance(start, date) or not isinstance(end, date):
                    logger.warning(
                        f"Invalid date range received from source {source_key}: start={start}, end={end}"
                    )
                    continue

                if SourceStrategy.ALL_TICKERS in source_strategy:
                    # CASE 1: ALL_TICKERS
                    if start > data_refresh_threshold:
                        logger.debug(
                            f"Skipping source {source_key} for {start} to {end} as it is beyond the refresh interval"
                        )
                        continue

                    f = executor.submit(
                        source.get_quotes,
                        start_date=start,
                        end_date=end,
                    )

                    futures.append((f, start, end))

                else:
                    # CASE 2: DEFAULT
                    f = executor.submit(
                        source.get_quotes,
                        *symbols,
                        start_date=start,
                        end_date=end,
                    )

                    futures.append((f, start, end))

            for future, start, end in futures:
                logger.debug(f"Received quotes from {source_key} for {start} to {end}")
                try:
                    new_quotes.append(handle_input(future.result(), schema=schema))

                    if SourceStrategy.ALL_TICKERS in source_strategy:
                        # Mark the quotes as available
                        mark_quotes_as_available(
                            source_key,
                            start_date=start,
                            end_date=end,
                        )
                except Exception:
                    logger.exception(f"Error getting quotes from {source_key}")

        if SourceStrategy.SINGLE_QUOTE in source_strategy:
            df_new = (
                pl.concat(new_quotes, how="vertical_relaxed")
                .select(
                    pl.col("symbol").cast(pl.String()),
                    pl.col("date").cast(pl.Date()),
                    pl.col("price").cast(pl.Decimal(scale=4)),
                )
                .collect()
            )
        else:
            df_new = (
                pl.concat(new_quotes, how="vertical_relaxed")
                .select(
                    pl.col("symbol").cast(pl.String()),
                    pl.col("date").cast(pl.Date()),
                    pl.col("open").cast(pl.Decimal(scale=4)),
                    pl.col("high").cast(pl.Decimal(scale=4)),
                    pl.col("low").cast(pl.Decimal(scale=4)),
                    pl.col("close").cast(pl.Decimal(scale=4)),
                )
                .collect()
            )

        if df_new.height > 0:
            # Update the quotes with the new data
            df_quotes_collected = df_quotes.collect()
            df_quotes_collected = df_quotes_collected.update(
                df_new, on=["symbol", "date"], how="full"
            ).sort("date")
            # Save the quotes to a local file
            save_quotes(df_quotes_collected, source_key)

            df_quotes = df_quotes_collected.lazy()

        df_quotes = df_quotes.filter(
            pl.col("symbol").is_in(symbols)
            & pl.col("date").is_between(actual_start_date, actual_end_date)
        )

        if SourceStrategy.SINGLE_QUOTE in source_strategy:
            return df_quotes.select(
                pl.col("symbol").cast(pl.String()),
                pl.col("date").cast(pl.Date()),
                pl.col("price").cast(pl.Decimal(scale=4)),
                pl.lit(source_key).alias("source_key"),
            ).collect()
        else:
            return df_quotes.select(
                pl.col("symbol").cast(pl.String()),
                pl.col("date").cast(pl.Date()),
                pl.col("open").cast(pl.Decimal(scale=4)),
                pl.col("high").cast(pl.Decimal(scale=4)),
                pl.col("low").cast(pl.Decimal(scale=4)),
                pl.col("close").cast(pl.Decimal(scale=4)),
                pl.lit(source_key).alias("source_key"),
            ).collect()

    @overload
    def get_quotes(
        self,
        *tickers: str,
        start_date: date = ...,
        end_date: date = ...,
        format: Literal[ReturnFormat.DICT] = ...,
    ) -> dict[str, list]: ...

    @overload
    def get_quotes(
        self,
        *tickers: str,
        start_date: date = ...,
        end_date: date = ...,
        format: Literal[ReturnFormat.PL_DATAFRAME] = ...,
    ) -> pl.DataFrame: ...

    @overload
    def get_quotes(
        self,
        *tickers: str,
        start_date: date = ...,
        end_date: date = ...,
        format: Literal[ReturnFormat.PL_LAZYFRAME] = ...,
    ) -> pl.LazyFrame: ...

    @overload
    def get_quotes(
        self,
        *tickers: str,
        start_date: date = ...,
        end_date: date = ...,
        format: Literal[ReturnFormat.PD_DATAFRAME] = ...,
    ) -> pd.DataFrame: ...

    @overload
    def get_quotes(
        self,
        *tickers: str,
        start_date: date = ...,
        end_date: date = ...,
        format: Literal[ReturnFormat.CSV, ReturnFormat.JSON] = ...,
    ) -> str: ...

    def get_quotes(
        self,
        *tickers: str | tuple[str, str],
        start_date: date | None = None,
        end_date: date | None = None,
        format: ReturnFormat | str = ReturnFormat.DICT,
        ohlc: bool = True,
        resample: timedelta | str | None = None,
    ) -> NiveshPyOutputType:
        """Get the quotes for the specified tickers.

        Args:
            tickers (str | Tuple[str, str]): The tickers to get quotes for.

                This can be a single symbol, a list of symbols, or a list of tuples
                containing the symbol and the source key.
                If source key is not specified, the pre-existing tickers are checked first.
                If not found, all out-dated sources are checked.

            start_date (date | None): The start date for the quotes (inclusive). If None, defaults to today.

            end_date (date | None): The end date for the quotes (inclusive). If None, defaults to today.
                The end date must be greater than or equal to the start date.

            format (ReturnFormat): The format of the returned tickers.
                Defaults to ReturnFormat.DICT. See [niveshpy.models.helpers.ReturnFormat] for available formats.

            ohlc (bool): If True, return OHLC data. If False, return single quotes.

            resample (timedelta | str | None): The resampling period.
                If specified, the quotes will be resampled to the specified period.
                This can be a polars-compatible string (e.g. "1d", "1w", "1mo") or a timedelta object.

        Returns:
            NiveshPyOutputType: The quotes in the specified format.

        Raises:
            ValueError: If the end date is before the start date.

        Examples:
            >>> nivesh = Nivesh()
            >>> quotes = nivesh.get_quotes("500209", "500210", ("500211", "amfi"))
        """
        schema = OHLC.get_polars_schema() if ohlc else Quote.get_polars_schema()

        if start_date and end_date and start_date > end_date:
            raise ValueError("Start date must be before end date")

        df_requested_tickers = (
            self._handle_tickers(*tickers) if len(tickers) > 0 else None
        )
        if df_requested_tickers is None:
            logger.warning(
                "No tickers requested. "
                "This will return quotes for all available tickers "
                "from all sources. This might take a long time."
            )

            df_requested_tickers = self.get_tickers(format=ReturnFormat.PL_DATAFRAME)
        elif df_requested_tickers.height == 0:
            logger.warning("No tickers found matching the requested symbols.")
            return format_output(
                schema.to_frame().with_columns(
                    source_key=pl.lit(None).cast(pl.String())
                ),
                format,
            )

        sources = self._get_sources(
            source_keys=df_requested_tickers.select("source_key")
            .unique()
            .to_series()
            .to_list()
        )

        quotes = [
            schema.to_frame(eager=True).with_columns(
                pl.lit(None).cast(pl.String()).alias("source_key")
            )
        ]

        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    self._get_quotes,
                    df_requested_tickers.filter(
                        pl.col("source_key") == pl.lit(source.get_source_key())
                    )
                    .select("symbol")
                    .to_series()
                    .to_list(),
                    source,
                    start_date,
                    end_date,
                ): source
                for source in sources
            }

            for future in futures:
                source = futures[future]
                try:
                    q = future.result()
                except Exception:
                    logger.exception(
                        f"Error getting quotes from {source.get_source_key()}"
                    )
                else:
                    if (
                        ohlc
                        and SourceStrategy.SINGLE_QUOTE
                        in source.get_source_config().source_strategy
                    ):
                        # If the source returns a single quote, we need to convert it to OHLC
                        # by duplicating the quote for open, high, low, and close
                        q = q.select(
                            pl.col("symbol").alias("symbol"),
                            pl.col("date").alias("date"),
                            pl.col("price").alias("open"),
                            pl.col("price").alias("high"),
                            pl.col("price").alias("low"),
                            pl.col("price").alias("close"),
                            pl.lit(source.get_source_key()).alias("source_key"),
                        )
                    elif (
                        not ohlc
                        and SourceStrategy.SINGLE_QUOTE
                        not in source.get_source_config().source_strategy
                    ):
                        # If the source returns OHLC data, we need to convert it to a single quote
                        # by taking only the close price
                        q = q.select(
                            pl.col("symbol").alias("symbol"),
                            pl.col("date").alias("date"),
                            pl.col("close").alias("price"),
                            pl.lit(source.get_source_key()).alias("source_key"),
                        )

                    quotes.append(q)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Quotes from source {source.get_source_key()}:")
                        logger.debug(q)

        df_final_quotes = pl.concat(quotes)

        if resample:
            if ohlc:
                df_final_quotes = df_final_quotes.group_by_dynamic(
                    "date",
                    every=resample,
                    group_by=["symbol", "source_key"],
                ).agg(
                    pl.col("open").first().alias("open"),
                    pl.col("high").max().alias("high"),
                    pl.col("low").min().alias("low"),
                    pl.col("close").last().alias("close"),
                )
            else:
                df_final_quotes = df_final_quotes.group_by_dynamic(
                    "date",
                    every=resample,
                    group_by=["symbol", "source_key"],
                ).agg(
                    pl.col("price")
                    .cast(pl.Float32())
                    .mean()
                    .cast(pl.Decimal(scale=4))
                    .alias("price"),
                )

        return format_output(df_final_quotes, format)

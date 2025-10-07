"""Utilities for styling outputs in NiveshPy."""

import polars as pl


def get_polars_print_config() -> pl.Config:
    """Get Polars print configuration for consistent DataFrame display."""
    return pl.Config(
        tbl_rows=-1,
        tbl_cols=-1,
        tbl_hide_column_data_types=True,
        tbl_hide_dataframe_shape=True,
        tbl_formatting="UTF8_BORDERS_ONLY",
        tbl_width_chars=-1,
    )

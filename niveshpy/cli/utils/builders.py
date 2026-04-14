"""Output builders for CLI commands."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.table import Table

    from niveshpy.cli.utils.models import Column, SectionBreak, TotalRow


def build_table(
    items: Iterable[Any | SectionBreak | TotalRow],
    columns: Sequence[Column],
    **kwargs: Any,
) -> Table:
    """Build a Rich Table from an iterable of items with section breaks and total rows."""
    from rich import box
    from rich.table import Table

    from niveshpy.cli.utils.models import SectionBreak, TotalRow

    table = Table(header_style="dim", box=box.SIMPLE, **kwargs)
    for column in columns:
        table.add_column(
            column.name,
            justify=column.justify,
            style=column.style,
        )

    for item in items:
        if isinstance(item, SectionBreak):
            table.add_section()
        elif isinstance(item, TotalRow):
            table.add_row(
                item.description,
                *([None] * (len(columns) - 2)),
                str(item.total),
                style="bold",
            )
        else:
            row = []
            for column in columns:
                value = getattr(item, column.key, None)
                row.append(column.format(value))
            table.add_row(*row)

    return table


def build_csv(
    items: Iterable[Mapping[str, Any]],
    *,
    fields: Sequence[str],
    output_file: Path | None = None,
) -> str | None:
    """Build CSV output from an iterable of items.

    Args:
        items: The rows to write to the CSV output.
        fields: The CSV field names to use for the header and row ordering.
        output_file: The file path to write the CSV output to. If not provided,
            the CSV content is built in memory and returned as a string.

    Returns:
        The CSV content as a string when ``output_file`` is not provided;
        otherwise, ``None`` after writing the CSV data to ``output_file``.
    """
    import csv
    from io import StringIO

    # If output_file is provided, write directly to the file.
    # Otherwise, build the CSV in memory and return it as a string.
    with output_file.open("w", newline="") if output_file else StringIO() as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(items)
        if isinstance(f, StringIO):
            return f.getvalue()

    return None

"""Output builders for CLI commands."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
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


def build_csv(items: Iterable[Mapping[str, Any]], *, fields: Sequence[str]) -> str:
    """Build a CSV string from an iterable of items."""
    import csv
    from io import StringIO

    f = StringIO()
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(items)
    return f.getvalue()

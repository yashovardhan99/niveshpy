"""CLI commands for reports."""

import datetime
import decimal
from typing import Literal

import click

from niveshpy.cli.utils import essentials, flags, output
from niveshpy.cli.utils.overrides import NiveshPyCommand
from niveshpy.core.query import tokens
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.models.report import (
    Holding,
    HoldingDisplay,
    HoldingExport,
    PerformanceDisplay,
)

DAYS_FOR_OLD = 15
"""Number of days after which holdings are considered old."""


def _has_date_query(queries: tuple[str, ...]) -> bool:
    """Check if any query in the tuple contains a date field."""
    return any(token == tokens.Keyword.Date for q in queries for token in QueryLexer(q))


@essentials.group()
def cli():
    """Group for report-related commands."""


@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("securities")
@flags.offset("securities")
@flags.output("format")
@click.option(
    "--total / --no-total",
    is_flag=True,
    help="Show overall total row in the report output.",
    default=True,
)
@essentials.command(parent=cli, cls=NiveshPyCommand)
def holdings(
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: output.OutputFormat,
    total: bool,
):
    """Generate holdings report.

    By default, generates a report of current holdings across all accounts.

    Optionally, provide text <queries> to filter securities, accounts, and dates.
    """
    # Generate report
    with output.loading_spinner("Generating holdings report..."):
        from niveshpy.services.report import get_holdings

        holdings = get_holdings(queries, limit, offset)

    # Warn if date filter is used — invested amounts don't respect date filters
    if _has_date_query(queries):
        output.display_warning(
            "Date filters apply to current value and units but not to invested "
            "amounts or gains, which always use the full transaction history. "
            "This will result in incorrect gains being reported."
        )

    if len(holdings) == 0:
        msg = (
            "No holdings found.\n"
            "Make sure you have added transactions for your securities"
            " and try syncing prices using 'niveshpy prices sync'."
        )
        output.display_warning(msg)
    else:
        extra_message = (
            f"Showing first {limit:,} holdings."
            if len(holdings) == limit and offset == 0
            else (
                f"Showing holdings {offset + 1:,} to {offset + len(holdings):,}."
                if offset > 0
                else None
            )
        )

        if any(
            h.date < (datetime.date.today() - datetime.timedelta(days=DAYS_FOR_OLD))
            for h in holdings
        ) and (not _has_date_query(queries)):
            output.display_warning(
                "Some holdings have not been updated recently. "
                "Consider syncing latest prices using 'niveshpy prices sync'."
            )

        if format == output.OutputFormat.TABLE:
            items: list[HoldingDisplay | output.TotalRow] = [
                HoldingDisplay.from_holding(h) for h in holdings
            ]

            if total:
                # Full portfolio metrics (XIRR, detailed totals) are
                # available via 'niveshpy reports performance'.
                from niveshpy.services.report import compute_portfolio_totals

                totals = compute_portfolio_totals(holdings)
                overall_total = output.TotalRow(
                    totals.total_gains
                    if totals.total_gains is not None
                    else totals.total_current_value,
                )
                items.append(overall_total)
            output.display_list(
                cls=HoldingDisplay,
                items=items,
                fmt=format,
                extra_message=extra_message,
            )
        elif format == output.OutputFormat.CSV:
            output.display_list(
                cls=HoldingExport,
                items=[HoldingExport.from_holding(h) for h in holdings],
                fmt=format,
                extra_message=extra_message,
            )
        else:
            output.display_list(
                cls=Holding,
                items=holdings,
                fmt=format,
                extra_message=extra_message,
            )


@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.output("format")
@click.option(
    "--type",
    "group_by",
    flag_value="type",
    help="Group allocation by security type.",
)
@click.option(
    "--category",
    "group_by",
    flag_value="category",
    help="Group allocation by security category.",
)
@click.option(
    "--both",
    "group_by",
    flag_value="both",
    default=True,
    hidden=True,
)
@essentials.command(parent=cli, cls=NiveshPyCommand)
def allocation(
    queries: tuple[str, ...],
    format: output.OutputFormat,
    group_by: Literal["both", "type", "category"],
):
    """Generate asset allocation report.

    By default, generates a report of current asset allocation
    grouped by security type and category.

    Optionally, provide text <queries> to filter securities, accounts, and dates.
    """
    # Generate report
    with output.loading_spinner("Generating allocation report..."):
        from niveshpy.services.report import get_allocation

        allocations = get_allocation(queries, group_by=group_by)
    if len(allocations) == 0:
        msg = (
            "No allocations found.\n"
            "Make sure you have added transactions for your securities"
            " and try syncing prices using 'niveshpy prices sync'."
        )
        output.display_warning(msg)
    else:
        output.display_list(
            cls=type(allocations[0]),
            items=allocations,
            fmt=format,
        )


@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.output("format")
@essentials.command(parent=cli, cls=NiveshPyCommand)
def performance(
    queries: tuple[str, ...],
    format: output.OutputFormat,
):
    """Generate portfolio performance report.

    Shows portfolio-level metrics including total current value, total invested,
    gains, and annualized returns (XIRR).

    Optionally, provide text <queries> to filter securities and accounts.
    """
    with output.loading_spinner("Generating performance report..."):
        from niveshpy.services.report import get_performance

        totals, xirr = get_performance(queries)

    # Convert gains_percentage from percentage (16.67) to fraction (0.1667)
    # for consistent :.2% formatting with xirr
    gains_pct = (
        (totals.gains_percentage / decimal.Decimal("100")).quantize(
            decimal.Decimal("0.0001")
        )
        if totals.gains_percentage is not None
        else None
    )

    display = PerformanceDisplay(
        total_current_value=totals.total_current_value,
        total_invested=totals.total_invested,
        absolute_gains=totals.total_gains,
        absolute_gains_pct=gains_pct,
        xirr=xirr,
    )

    output.display_list(cls=PerformanceDisplay, items=[display], fmt=format)

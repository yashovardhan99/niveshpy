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
    PerformanceHolding,
    PerformanceHoldingDisplay,
    PerformanceHoldingExport,
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
            "amounts, which always use the full transaction history."
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
                total_value = sum((h.amount for h in holdings), decimal.Decimal("0"))
                items.append(output.TotalRow(total_value))

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
def performance(
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: output.OutputFormat,
    total: bool,
):
    """Generate portfolio performance report.

    Shows per-holding performance metrics including current value, invested,
    gains, and annualized returns (XIRR) for each (account, security) pair.

    Optionally, provide text <queries> to filter securities and accounts.
    """
    with output.loading_spinner("Generating performance report..."):
        from niveshpy.services.report import get_performance

        result = get_performance(queries, limit=limit, offset=offset)

    if len(result.holdings) == 0:
        msg = (
            "No holdings found.\n"
            "Make sure you have added transactions for your securities"
            " and try syncing prices using 'niveshpy prices sync'."
        )
        output.display_warning(msg)
        return

    extra_message = (
        f"Showing first {limit:,} holdings."
        if len(result.holdings) == limit and offset == 0
        else (
            f"Showing holdings {offset + 1:,} to {offset + len(result.holdings):,}."
            if offset > 0
            else None
        )
    )

    if format == output.OutputFormat.TABLE:
        items: list[
            PerformanceHoldingDisplay | output.SectionBreak | output.TotalRow
        ] = [PerformanceHoldingDisplay.from_holding(h) for h in result.holdings]

        if total:
            gains_pct = _compute_gains_pct_fraction(result.totals.gains_percentage)
            total_row = PerformanceHoldingDisplay(
                account="",
                security="Total",
                current_value=result.totals.total_current_value,
                invested=result.totals.total_invested,
                gains=result.totals.total_gains,
                gains_pct=gains_pct,
                xirr=result.totals.xirr,
            )
            items.append(output.SectionBreak())
            items.append(total_row)

        output.display_list(
            cls=PerformanceHoldingDisplay,
            items=items,
            fmt=format,
            extra_message=extra_message,
        )
    elif format == output.OutputFormat.CSV:
        output.display_list(
            cls=PerformanceHoldingExport,
            items=[PerformanceHoldingExport.from_holding(h) for h in result.holdings],
            fmt=format,
            extra_message=extra_message,
        )
    else:
        output.display_list(
            cls=PerformanceHolding,
            items=result.holdings,
            fmt=format,
            extra_message=extra_message,
        )


def _compute_gains_pct_fraction(
    gains_percentage: decimal.Decimal | None,
) -> decimal.Decimal | None:
    """Convert gains percentage (e.g. 16.67) to fraction (0.1667) for :.2% formatting."""
    if gains_percentage is None:
        return None
    return (gains_percentage / decimal.Decimal("100")).quantize(
        decimal.Decimal("0.0001")
    )

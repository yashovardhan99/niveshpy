"""CLI commands for reports."""

import datetime
import decimal
import textwrap
from typing import Literal

import click

from niveshpy.cli.utils import essentials, flags, output
from niveshpy.cli.utils.display import (
    capture_for_pager,
    display,
    display_json,
    display_warning,
    loading_spinner,
)
from niveshpy.cli.utils.formatters import format_decimal, format_percentage
from niveshpy.cli.utils.models import OutputFormat, SectionBreak, TotalRow
from niveshpy.cli.utils.overrides import NiveshPyCommand
from niveshpy.core.logging import logger
from niveshpy.core.query import tokens
from niveshpy.core.query.tokenizer import QueryLexer

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
    format: OutputFormat,
    total: bool,
):
    """Generate holdings report.

    By default, generates a report of current holdings across all accounts.

    Optionally, provide text <queries> to filter securities, accounts, and dates.
    """
    logger.debug("Running holdings command with %d queries", len(queries))
    from niveshpy.models.report import (
        Holding,
        HoldingDisplay,
        HoldingExport,
    )

    # Generate report
    with loading_spinner("Generating holdings report..."):
        from niveshpy.services.report import get_holdings

        holdings = get_holdings(queries, limit, offset)

    # Warn if date filter is used — invested amounts don't respect date filters
    if _has_date_query(queries):
        display_warning(
            "Date filters apply to current value and units but not to invested "
            "amounts, which always use the full transaction history."
        )

    if len(holdings) == 0:
        msg = (
            "No holdings found.\n"
            "Make sure you have added transactions for your securities"
            " and try syncing prices using 'niveshpy prices sync'."
        )
        display_warning(msg)
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
            display_warning(
                "Some holdings have not been updated recently. "
                "Consider syncing latest prices using 'niveshpy prices sync'."
            )

        if format == OutputFormat.TABLE:
            items: list[HoldingDisplay | TotalRow] = [
                HoldingDisplay.from_holding(h) for h in holdings
            ]

            if total:
                total_value = sum((h.amount for h in holdings), decimal.Decimal("0"))
                items.append(TotalRow(total_value))

            output.display_list(
                cls=HoldingDisplay,
                items=items,
                fmt=format,
                extra_message=extra_message,
            )
        elif format == OutputFormat.CSV:
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
    format: OutputFormat,
    group_by: Literal["both", "type", "category"],
):
    """Generate asset allocation report.

    By default, generates a report of current asset allocation
    grouped by security type and category.

    Optionally, provide text <queries> to filter securities, accounts, and dates.
    """
    logger.debug(
        "Running allocation command with %d queries, group_by=%s",
        len(queries),
        group_by,
    )
    # Generate report
    with loading_spinner("Generating allocation report..."):
        from niveshpy.services.report import get_allocation

        allocations = get_allocation(queries, group_by=group_by)
    if len(allocations) == 0:
        msg = (
            "No allocations found.\n"
            "Make sure you have added transactions for your securities"
            " and try syncing prices using 'niveshpy prices sync'."
        )
        display_warning(msg)
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
    format: OutputFormat,
    total: bool,
):
    """Generate portfolio performance report.

    Shows per-holding performance metrics including current value, invested,
    gains, and annualized returns (XIRR) for each (account, security) pair.

    Optionally, provide text <queries> to filter securities and accounts.
    """
    from niveshpy.models.report import (
        PerformanceHolding,
        PerformanceHoldingDisplay,
        PerformanceHoldingExport,
    )

    logger.debug("Running performance command with %d queries", len(queries))
    with loading_spinner("Generating performance report..."):
        from niveshpy.services.report import get_performance

        result = get_performance(queries, limit=limit, offset=offset)

    if len(result.holdings) == 0:
        msg = (
            "No holdings found.\n"
            "Make sure you have added transactions for your securities"
            " and try syncing prices using 'niveshpy prices sync'."
        )
        display_warning(msg)
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

    if format == OutputFormat.TABLE:
        items: list[PerformanceHoldingDisplay | SectionBreak | TotalRow] = [
            PerformanceHoldingDisplay.from_holding(h) for h in result.holdings
        ]

        if total:
            gains_pct = result.totals.gains_percentage
            total_row = PerformanceHoldingDisplay(
                account="[not dim bold]Total",
                security="",
                date=None,
                current_value=result.totals.total_current_value,
                invested=result.totals.total_invested,
                gains=result.totals.total_gains,
                gains_pct=gains_pct,
                xirr=result.totals.xirr,
            )
            items.append(SectionBreak())
            items.append(total_row)

        output.display_list(
            cls=PerformanceHoldingDisplay,
            items=items,
            fmt=format,
            extra_message=extra_message,
        )
    elif format == OutputFormat.CSV:
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


@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.output("format", allowed=[OutputFormat.TABLE, OutputFormat.JSON])
@essentials.command(parent=cli, cls=NiveshPyCommand)
def summary(
    queries: tuple[str, ...],
    format: Literal[OutputFormat.TABLE, OutputFormat.JSON],
):
    """Generate portfolio summary report.

    Shows overall summary metrics like total current value, invested, gains,
    and XIRR, along with top holdings and allocation breakdown.

    Optionally, provide text <queries> to filter securities and accounts.
    """
    logger.debug("Running summary command with %d queries", len(queries))
    with loading_spinner("Generating portfolio summary..."):
        from niveshpy.services.report import get_summary

        result = get_summary(queries)

    if len(result.top_holdings) == 0:
        if len(queries) > 0:
            msg = (
                "No holdings found for the given filters.\n"
                "Make sure your queries are correct and try syncing prices using "
                "'niveshpy prices sync'."
            )
            display_warning(msg)
        else:
            msg = (
                "Welcome to [bold]NiveshPy[/bold].\n"
                "To get started, add transactions for your securities using 'niveshpy transactions add'"
                " and try syncing prices using 'niveshpy prices sync'.\n"
                "You can also import transactions from your preferred source using 'niveshpy parse ...'"
            )
            display(msg)

    else:
        if format == OutputFormat.TABLE:
            from rich import box
            from rich.bar import Bar
            from rich.padding import Padding
            from rich.panel import Panel
            from rich.table import Table

            from niveshpy.models.security import category_format_map

            # Metrics Section
            metrics = Table(show_header=False, box=box.SIMPLE)
            metrics.add_column(min_width=40)
            metrics.add_column(justify="right", style="bold")
            metrics.add_column(justify="right", style="bold")
            metrics.add_row(
                "Total Current Value",
                format_decimal(result.metrics.total_current_value),
            )
            metrics.add_row(
                "Total Invested", format_decimal(result.metrics.total_invested)
            )
            gains = format_decimal(result.metrics.total_gains)
            gains_pct = format_percentage(result.metrics.gains_percentage)
            metrics.add_row(
                "Absolute Gains", f"[green]{gains}", f"[green]({gains_pct})"
            )
            xirr = format_percentage(result.metrics.xirr)
            metrics.add_row("XIRR (%)", f"[green]{xirr}")

            subtitle = []
            if len(queries) > 1:
                subtitle.append(f"{len(queries)} queries applied")
            elif len(queries) == 1:
                subtitle.append(
                    textwrap.shorten(f"Query: {queries[0]}", 20, placeholder="...")
                )
            if result.metrics.last_updated:
                subtitle.append(f"Last Updated: {result.metrics.last_updated:%d %b %Y}")

            top_panel = Panel.fit(
                metrics,
                title="Portfolio Summary",
                border_style="green"
                if result.metrics.total_gains and result.metrics.total_gains >= 0
                else "red",
                subtitle=" | ".join(subtitle) if subtitle else None,
            )

            # Top Holdings
            holdings: Table = Table(title="Top Holdings", box=box.SIMPLE)
            holdings.add_column(
                "Account", style="dim", no_wrap=True, max_width=20, min_width=0
            )
            holdings.add_column(
                "Security", style="bold", no_wrap=True, max_width=30, min_width=20
            )
            holdings.add_column("Current Value", justify="right", min_width=10)
            holdings.add_column("XIRR", justify="right", min_width=7)
            for h in result.top_holdings:
                holdings.add_row(
                    f"{h.account.name} ({h.account.institution})",
                    h.security.name,
                    format_decimal(h.current_value),
                    format_percentage(h.xirr),
                )

            # Allocation Breakdown
            allocation: Table = Table(
                title="Asset Allocation", box=box.SIMPLE, leading=1
            )
            allocation.add_column("Category", no_wrap=True)
            allocation.add_column("Weight", justify="right", style="bold")
            allocation.add_column("", justify="left", no_wrap=True, width=30)
            for a in result.allocation:
                allocation.add_row(
                    category_format_map.get(a.security_category.value),
                    format_percentage(a.allocation),
                    Bar(1, 0, float(a.allocation), color="white"),
                )

            # Display group
            with capture_for_pager():
                display(top_panel)
                display(Padding(holdings, (2, 0)))
                display(allocation)
        else:
            with capture_for_pager():
                display_json(result.model_dump_json())

"""CLI commands for reports."""

import datetime
import decimal
import json
import textwrap
from pathlib import Path
from typing import Literal

import click

from niveshpy.cli.models.report import (
    AllocationDisplay,
    PerformanceHoldingDisplay,
    SummaryResultDisplay,
)
from niveshpy.cli.utils import essentials, flags
from niveshpy.cli.utils.builders import build_csv, build_table
from niveshpy.cli.utils.display import (
    capture_for_pager,
    display,
    display_json,
    display_warning,
    loading_spinner,
)
from niveshpy.cli.utils.formatters import (
    format_account,
    format_date,
    format_decimal,
    format_percentage,
    format_security,
    format_security_category,
)
from niveshpy.cli.utils.models import Column, OutputFormat, SectionBreak, TotalRow
from niveshpy.cli.utils.overrides import NiveshPyCommand
from niveshpy.core.app import AppState
from niveshpy.core.converter import get_csv_converter, get_json_converter
from niveshpy.core.logging import logger
from niveshpy.core.query import tokens
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.models.report import Holding

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
@flags.output_file()
@click.option(
    "--total / --no-total",
    is_flag=True,
    help="Show overall total row in the report output.",
    default=True,
)
@essentials.command(parent=cli, cls=NiveshPyCommand)
@click.pass_context
def holdings(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: OutputFormat,
    output_file: Path | None,
    total: bool,
):
    """Generate holdings report.

    By default, generates a report of current holdings across all accounts.

    Optionally, provide text <queries> to filter securities, accounts, and dates.
    """
    logger.debug("Running holdings command with %d queries", len(queries))

    # Generate report
    with loading_spinner("Generating holdings report..."):
        state = ctx.ensure_object(AppState)
        holdings = state.app.report_service.get_holdings(
            queries, limit=limit, offset=offset
        )

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

        with capture_for_pager(
            enabled=output_file is None or format == OutputFormat.TABLE
        ):
            if format == OutputFormat.TABLE:
                items: list[Holding | TotalRow] = list(holdings)
                if total:
                    total_value = sum(
                        (h.amount for h in holdings), decimal.Decimal("0")
                    )
                    items.append(TotalRow(format_decimal(total_value)))

                if extra_message:
                    display(extra_message)

                if output_file:
                    display_warning(
                        "Output file specified, but table format does not support file output. Ignoring --output-file flag."
                    )

                columns = [
                    Column("account", style="dim", formatter=format_account),
                    Column("security", style="bold", formatter=format_security),
                    Column("date", style="cyan", formatter=format_date),
                    Column(
                        "units", style="dim", formatter=format_decimal, justify="right"
                    ),
                    Column(
                        "invested",
                        style="dim",
                        formatter=format_decimal,
                        justify="right",
                    ),
                    Column(
                        "amount",
                        name="current",
                        style="bold",
                        formatter=format_decimal,
                        justify="right",
                    ),
                ]

                table = build_table(items, columns)
                display(table)
            elif format == OutputFormat.CSV:
                c = get_csv_converter()
                csv = build_csv(
                    c.unstructure(holdings),
                    fields=[
                        "account",
                        "security",
                        "date",
                        "units",
                        "invested",
                        "current",
                    ],
                    output_file=output_file,
                )
                if csv:
                    display(csv)
            elif format == OutputFormat.JSON:
                c = get_json_converter()
                data = c.unstructure(holdings)
                if output_file:
                    with output_file.open("w") as f:
                        json.dump(data, f, indent=4)
                else:
                    display_json(data=data)


@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.output("format")
@flags.output_file()
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
@click.pass_context
def allocation(
    ctx: click.Context,
    queries: tuple[str, ...],
    format: OutputFormat,
    output_file: Path | None,
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
        state = ctx.ensure_object(AppState)
        allocations = state.app.report_service.get_allocation(
            queries, group_by=group_by
        )
    if len(allocations) == 0:
        msg = (
            "No allocations found.\n"
            "Make sure you have added transactions for your securities"
            " and try syncing prices using 'niveshpy prices sync'."
        )
        display_warning(msg)
    else:
        items = map(AllocationDisplay.from_domain, allocations)
        with capture_for_pager(
            enabled=output_file is None or format == OutputFormat.TABLE
        ):
            if format == OutputFormat.TABLE:
                table = build_table(items, AllocationDisplay.get_columns(group_by))

                if output_file:
                    display_warning(
                        "Output file specified, but table format does not support file output. Ignoring --output-file flag."
                    )

                display(table)
            elif format == OutputFormat.CSV:
                csv = build_csv(
                    map(AllocationDisplay.to_csv_dict, items),
                    fields=AllocationDisplay.get_csv_fields(group_by),
                    output_file=output_file,
                )
                if csv:
                    display(csv)
            elif format == OutputFormat.JSON:
                data = [a.to_json_dict() for a in items]
                if output_file:
                    with output_file.open("w") as f:
                        json.dump(data, f, indent=4)
                else:
                    display_json(data=data)


@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("securities")
@flags.offset("securities")
@flags.output("format")
@flags.output_file()
@click.option(
    "--total / --no-total",
    is_flag=True,
    help="Show overall total row in the report output.",
    default=True,
)
@essentials.command(parent=cli, cls=NiveshPyCommand)
@click.pass_context
def performance(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: OutputFormat,
    output_file: Path | None,
    total: bool,
):
    """Generate portfolio performance report.

    Shows per-holding performance metrics including current value, invested,
    gains, and annualized returns (XIRR) for each (account, security) pair.

    Optionally, provide text <queries> to filter securities and accounts.
    """
    logger.debug("Running performance command with %d queries", len(queries))
    with loading_spinner("Generating performance report..."):
        state = ctx.ensure_object(AppState)

        result = state.app.report_service.get_performance(
            queries, limit=limit, offset=offset
        )

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

    items = map(PerformanceHoldingDisplay.from_domain, result.holdings)

    with capture_for_pager(enabled=output_file is None or format == OutputFormat.TABLE):
        if format == OutputFormat.TABLE:
            table_items: list[PerformanceHoldingDisplay | SectionBreak | TotalRow] = (
                list(items)
            )
            if extra_message:
                display(extra_message)

            if output_file:
                display_warning(
                    "Output file specified, but table format does not support file output. Ignoring --output-file flag."
                )

            if total:
                total_row = TotalRow(
                    total=format_percentage(result.totals.xirr),
                    description="Overall XIRR",
                )
                table_items.append(SectionBreak())
                table_items.append(total_row)

            table = build_table(table_items, PerformanceHoldingDisplay.columns)
            display(table)
        elif format == OutputFormat.CSV:
            csv = build_csv(
                map(PerformanceHoldingDisplay.to_csv_dict, items),
                fields=PerformanceHoldingDisplay.csv_fields,
                output_file=output_file,
            )
            if csv:
                display(csv)
        elif format == OutputFormat.JSON:
            data = [h.to_json_dict() for h in items]
            if output_file:
                with output_file.open("w") as f:
                    json.dump(data, f, indent=4)
            else:
                display_json(data=data)


@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.output("format", allowed=[OutputFormat.TABLE, OutputFormat.JSON])
@flags.output_file()
@essentials.command(parent=cli, cls=NiveshPyCommand)
@click.pass_context
def summary(
    ctx: click.Context,
    queries: tuple[str, ...],
    format: Literal[OutputFormat.TABLE, OutputFormat.JSON],
    output_file: Path | None,
):
    """Generate portfolio summary report.

    Shows overall summary metrics like total current value, invested, gains,
    and XIRR, along with top holdings and allocation breakdown.

    Optionally, provide text <queries> to filter securities and accounts.
    """
    logger.debug("Running summary command with %d queries", len(queries))
    with loading_spinner("Generating portfolio summary..."):
        state = ctx.ensure_object(AppState)
        result = state.app.report_service.get_summary(queries)

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
        display_result = SummaryResultDisplay.from_domain(result)

        if format == OutputFormat.TABLE:
            from rich import box
            from rich.bar import Bar
            from rich.padding import Padding
            from rich.panel import Panel
            from rich.table import Table

            # Metrics Section
            metrics = Table(show_header=False, box=box.SIMPLE)
            metrics.add_column(min_width=40)
            metrics.add_column(justify="right", style="bold")
            metrics.add_column(justify="right", style="bold")
            metrics.add_row(
                "Total Current Value",
                format_decimal(display_result.metrics.total_current_value),
            )
            metrics.add_row(
                "Total Invested", format_decimal(display_result.metrics.total_invested)
            )
            gains = format_decimal(display_result.metrics.total_gains)
            gains_pct = format_percentage(display_result.metrics.gains_percentage)
            metrics.add_row(
                "Absolute Gains", f"[green]{gains}", f"[green]({gains_pct})"
            )
            xirr = format_percentage(display_result.metrics.xirr)
            metrics.add_row("XIRR (%)", f"[green]{xirr}")

            subtitle = []
            if len(queries) > 1:
                subtitle.append(f"{len(queries)} queries applied")
            elif len(queries) == 1:
                subtitle.append(
                    textwrap.shorten(f"Query: {queries[0]}", 20, placeholder="...")
                )
            if display_result.metrics.last_updated:
                subtitle.append(
                    f"Last Updated: {display_result.metrics.last_updated:%d %b %Y}"
                )

            top_panel = Panel.fit(
                metrics,
                title="Portfolio Summary",
                border_style=(
                    "green"
                    if display_result.metrics.total_gains
                    and display_result.metrics.total_gains >= 0
                    else "red"
                ),
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
            holdings.add_column("XIRR", justify="right", min_width=7, style="bold")
            for h in display_result.top_holdings:
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
            for a in display_result.allocation:
                allocation.add_row(
                    (
                        format_security_category(a.security_category)
                        if a.security_category
                        else None
                    ),
                    format_percentage(a.allocation),
                    Bar(1, 0, float(a.allocation), color="white"),
                )

            # Display group
            with capture_for_pager():
                if output_file:
                    display_warning(
                        "Output file specified, but table format does not support file output. Ignoring --output-file flag."
                    )
                display(top_panel)
                display(Padding(holdings, (2, 0)))
                display(allocation)
        else:
            with capture_for_pager(enabled=output_file is None):
                data = display_result.to_json_dict()
                if output_file:
                    with output_file.open("w") as f:
                        json.dump(data, f, indent=4)
                else:
                    display_json(data=data)

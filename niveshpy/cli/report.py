"""CLI commands for reports."""

import datetime
import decimal
from typing import Literal

import click

from niveshpy.cli.utils import essentials, flags, output
from niveshpy.models.report import Holding, HoldingDisplay, HoldingExport

DAYS_FOR_OLD = 15
"""Number of days after which holdings are considered old."""


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
@essentials.command(parent=cli)
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
        ) and ("date:" not in " ".join(queries).lower()):
            output.display_warning(
                "Some holdings have not been updated recently. "
                "Consider syncing latest prices using 'niveshpy prices sync'."
            )

        if format == output.OutputFormat.TABLE:
            items: list[HoldingDisplay | output.TotalRow] = [
                HoldingDisplay.from_holding(h) for h in holdings
            ]

            if total:
                overall_total = output.TotalRow(
                    sum((h.amount for h in holdings), decimal.Decimal("0")),
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
@essentials.command(parent=cli)
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

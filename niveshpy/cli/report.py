"""CLI commands for reports."""

import decimal

import click

from niveshpy.cli.utils import essentials, flags, output
from niveshpy.models.report import Holding, HoldingDisplay, HoldingExport


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

    extra_message = (
        f"Showing first {limit:,} holdings."
        if len(holdings) == limit and offset == 0
        else (
            f"Showing holdings {offset + 1:,} to {offset + len(holdings):,}."
            if offset > 0
            else None
        )
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

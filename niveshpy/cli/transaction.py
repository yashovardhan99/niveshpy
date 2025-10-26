"""CLI API for transactions."""

import click
from niveshpy.cli.utils import flags
from niveshpy.cli.utils.overrides import command, group
from niveshpy.cli.app import AppState
from niveshpy.db.database import DatabaseError
from niveshpy.models.transaction import (
    TransactionRead,
)
from niveshpy.cli.utils.style import (
    OutputFormat,
    console,
    error_console,
    format_dataframe,
    rich_click_pager,
)
from niveshpy.core.logging import logger


@group(invoke_without_command=True)
@flags.common_options
@click.pass_context
def transactions(ctx: click.Context) -> None:
    """List, add, or delete transactions."""
    if ctx.invoked_subcommand is None:
        ctx.forward(show)


@command("list")
@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("accounts", default=30)
@flags.output("format")
@flags.common_options
@click.pass_context
def show(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    format: OutputFormat,
) -> None:
    """List all transactions.

    Optionally provide a text QUERY to filter transactions by various attributes.

    Examples:
        niveshpy transactions
        niveshpy transactions list gold # Filter by a security with 'gold' in its name or key
        niveshpy transactions list acct:Z123 # Filter by account 'Z123'
        niveshpy transactions list type:purchase # Filter by transaction type 'purchase'

    View the documentation at https://yashovardhan99.github.io/niveshpy/cli/queries/ for more details on query syntax.
    """
    state = ctx.ensure_object(AppState)
    with error_console.status("Loading transactions..."):
        try:
            result = state.app.transaction.list_transactions(
                queries=queries, limit=limit
            )
        except DatabaseError as e:
            logger.critical(e, exc_info=True)
            ctx.exit(1)
        except ValueError as e:
            logger.error(e, exc_info=True)
            ctx.exit(1)
        if result.total == 0:
            msg = "No transactions " + (
                "match your query." if queries else "found in the database."
            )
            error_console.print(msg, style="yellow")
            ctx.exit()

        out = format_dataframe(result.data, format, TransactionRead.rich_format_map())

    with rich_click_pager(console):
        if result.total > limit and console.is_terminal:
            console.print(
                f"Showing {limit:,} of {result.total:,} transactions.", style="yellow"
            )
        console.print_json(out) if format == OutputFormat.JSON and isinstance(
            out, str
        ) else console.print(out)


transactions.add_command(show)

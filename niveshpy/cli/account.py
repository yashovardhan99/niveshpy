"""CLI commands for managing accounts."""

import click

from niveshpy.cli.utils import flags
from niveshpy.cli.utils.overrides import command, group
from niveshpy.cli.app import AppState
from niveshpy.cli.utils.style import (
    OutputFormat,
    console,
    error_console,
    format_dataframe,
    rich_click_pager,
)
from niveshpy.core.logging import logger
from niveshpy.db.database import DatabaseError
from niveshpy.models.account import AccountRead


@group(invoke_without_command=True)
@click.pass_context
def accounts(ctx: click.Context) -> None:
    """Manage accounts."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(show)


@command("list")
@click.argument("query", default="", required=False, metavar="[<query>]")
@flags.limit("accounts", default=30)
@flags.output("format")
@flags.common_options
@click.pass_context
def show(ctx: click.Context, query: str, limit: int, format: OutputFormat) -> None:
    """List all accounts.

    An optional QUERY can be provided to filter accounts by name or institution.
    """
    state = ctx.ensure_object(AppState)
    with error_console.status("Loading accounts..."):
        try:
            result = state.app.account.list_accounts(query=query, limit=limit)
        except ValueError as e:
            logger.error(e, exc_info=True)
            ctx.exit(1)
        except DatabaseError as e:
            logger.critical(e, exc_info=True)
            ctx.exit(1)

        if result.total == 0:
            msg = "No accounts " + (
                "match your query." if query else "found in the database."
            )
            error_console.print(msg, style="yellow")
            ctx.exit()

        out = format_dataframe(result.data, format, AccountRead.rich_format_map())

    with rich_click_pager(console):
        if result.total > limit and console.is_terminal:
            console.print(
                f"Showing {limit:,} of {result.total:,} accounts.", style="yellow"
            )
        console.print_json(out) if format == OutputFormat.JSON and isinstance(
            out, str
        ) else console.print(out)


# @command()
# @click.pass_obj
# def add(state: AppState) -> None:
#     """Add a new account."""
#     console.print(
#         dedent("""
#                Adding new account.
#                Any command-line arguments will be used as defaults.
#                Use Ctrl+Z to skip optional fields.
#                Use Ctrl+C to cancel.
#                """)
#     )
#     inquirer_style = get_style({}, style_override=state.no_color)
#     name = inquirer.text(
#         message="Account Name",
#         validate=EmptyInputValidator(),
#         style=inquirer_style,
#     ).execute()
#     institution = inquirer.text(
#         message="Institution Name",
#         validate=EmptyInputValidator(),
#         style=inquirer_style,
#     ).execute()
#     account = AccountWrite(
#         name=name,
#         institution=institution,
#     )
#     state.app.account.add_accounts([account])
#     console.print(f"Account [b]{name}[/b] added successfully.", style="green")


accounts.add_command(show)
# accounts.add_command(add)

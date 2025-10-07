"""CLI commands for managing accounts."""

from textwrap import dedent
import click

from niveshpy.cli.utils.overrides import command, group
from niveshpy.models.account import AccountWrite
from niveshpy.cli.app import AppState
from InquirerPy import inquirer, get_style
from InquirerPy.validator import EmptyInputValidator
from niveshpy.cli.utils.style import console


@group(invoke_without_command=True)
@click.pass_context
def accounts(ctx: click.Context) -> None:
    """Manage accounts."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(show)


@command("list")
@click.pass_obj
def show(state: AppState) -> None:
    """Show all Accounts."""
    console.print(state.app.account_service.get_accounts())


@command()
@click.pass_obj
def add(state: AppState) -> None:
    """Add a new account."""
    console.print(
        dedent("""
               Adding new account.
               Any command-line arguments will be used as defaults.
               Use Ctrl+Z to skip optional fields.
               Use Ctrl+C to cancel.
               """)
    )
    inquirer_style = get_style({}, style_override=state.no_color)
    name = inquirer.text(
        message="Account Name",
        validate=EmptyInputValidator(),
        style=inquirer_style,
    ).execute()
    institution = inquirer.text(
        message="Institution Name",
        validate=EmptyInputValidator(),
        style=inquirer_style,
    ).execute()
    account = AccountWrite(
        name=name,
        institution=institution,
    )
    state.app.account_service.add_accounts([account])
    console.print(f"Account [b]{name}[/b] added successfully.", style="green")


accounts.add_command(show)
accounts.add_command(add)

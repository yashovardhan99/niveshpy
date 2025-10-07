"""CLI commands for managing accounts."""

from textwrap import dedent
import click

from niveshpy.cli.utils.overrides import command, group
from niveshpy.models.account import AccountWrite
from niveshpy.cli.app import AppState
from InquirerPy import inquirer
from InquirerPy.validator import EmptyInputValidator


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
    click.echo(state.app.account_service.get_accounts())


@command()
@click.pass_obj
def add(state: AppState) -> None:
    """Add a new account."""
    click.echo(
        dedent("""
               Adding new account.
               Any command-line arguments will be used as defaults.
               Use Ctrl+Z to skip optional fields.
               Use Ctrl+C to cancel.
               """)
    )
    name = inquirer.text(
        message="Account Name",
        validate=EmptyInputValidator(),
    ).execute()
    institution = inquirer.text(
        message="Institution Name",
        validate=EmptyInputValidator(),
    ).execute()
    account = AccountWrite(
        name=name,
        institution=institution,
    )
    state.app.account_service.add_accounts([account])
    click.secho(f"Account '{name}' added successfully.", fg="green")


accounts.add_command(show)
accounts.add_command(add)

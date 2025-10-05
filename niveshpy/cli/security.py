"""CLI commands for managing securities."""

from textwrap import dedent
import click

from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.services.app import Application
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import EmptyInputValidator


@click.group(invoke_without_command=True)
@click.pass_context
def securities(ctx: click.Context) -> None:
    """Manage securities."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(show)


@securities.command("list")
@click.pass_obj
def show(app: Application) -> None:
    """Show all securities."""
    click.echo(app.security_service.get_securities())


@securities.command()
@click.pass_obj
def add(app: Application) -> None:
    """Add a new security."""
    click.echo(
        dedent("""
               Adding new security.
               Any command-line arguments will be used as defaults.
               Use Ctrl+Z to skip optional fields.
               Use Ctrl+C to cancel.
               """)
    )
    security_key = inquirer.text(
        message="Security Key",
        instruction="(A unique identifier for the security, e.g., ticker symbol or ISIN)",
        validate=EmptyInputValidator(),
    ).execute()
    name = inquirer.text(
        message="Security Name",
        instruction="(The full name of the security)",
        validate=EmptyInputValidator(),
    ).execute()
    category = inquirer.select(
        message="Security Category",
        choices=[Choice(cat, name=cat.name) for cat in SecurityCategory],
    ).execute()
    security_type = inquirer.select(
        message="Security Type",
        choices=[Choice(t, name=t) for t in SecurityType],
    ).execute()

    security = Security(
        key=security_key,
        name=name,
        category=category,
        type=security_type,
    )
    print(security)
    app.security_service.add_securities([security])
    click.secho(f"Security '{name}' added successfully.", fg="green")

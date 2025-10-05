"""Main CLI entry point for Niveshpy."""

import sys
import click

from niveshpy.cli.account import accounts
from niveshpy.cli.security import securities
from niveshpy.db import Database
from niveshpy.services.app import Application
from niveshpy.cli.transaction import transactions


@click.group()
@click.version_option(prog_name="NiveshPy")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Simple CLI command to greet the user."""
    db = Database()
    ctx.with_resource(db)
    application = Application(db)
    ctx.obj = application


cli.add_command(transactions)
cli.add_command(securities)
cli.add_command(accounts)

if __name__ == "__main__":
    sys.exit(cli())

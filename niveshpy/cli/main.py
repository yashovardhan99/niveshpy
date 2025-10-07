"""Main CLI entry point for Niveshpy."""

import sys
import click

from niveshpy.cli.app import AppState, Application
from niveshpy.cli.account import accounts
from niveshpy.cli.security import securities
from niveshpy.cli.utils import flags
from niveshpy.cli.utils.overrides import group
from niveshpy.db.database import Database
from niveshpy.cli.transaction import transactions


@group()
@click.version_option(prog_name="NiveshPy")
@flags.common_options
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Simple CLI command to greet the user."""
    db = Database()
    ctx.with_resource(db)
    application = Application(db)
    ctx.ensure_object(AppState).app = application


cli.add_command(transactions)
cli.add_command(securities)
cli.add_command(accounts)

if __name__ == "__main__":
    sys.exit(cli())

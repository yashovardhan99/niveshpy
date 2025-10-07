"""Main CLI entry point for Niveshpy."""

import sys
import click

from niveshpy.cli.app import AppState, Application
from niveshpy.cli.account import accounts
from niveshpy.cli.security import securities
from niveshpy.cli.utils import flags
from niveshpy.cli.utils.overrides import group
from niveshpy.cli.utils import logging
from niveshpy.db.database import Database
from niveshpy.cli.transaction import transactions
from niveshpy.cli.utils.style import error_console, console


@group()
@flags.common_options
@flags.debug()
@flags.no_color()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Simple CLI command to greet the user."""
    state = ctx.ensure_object(AppState)

    if state.no_color:
        console.no_color = True
        error_console.no_color = True

    logging.setup(state.debug, error_console)  # Initialize logging with debug flag
    db = Database()
    ctx.with_resource(db)
    application = Application(db)
    state.app = application


cli.add_command(transactions)
cli.add_command(securities)
cli.add_command(accounts)

if __name__ == "__main__":
    sys.exit(cli())

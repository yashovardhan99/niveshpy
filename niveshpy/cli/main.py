"""Main CLI entry point for Niveshpy."""

import sys
import click

from niveshpy.cli import parse
from niveshpy.core.app import AppState, Application
from niveshpy.cli.account import accounts
from niveshpy.cli.security import securities
from niveshpy.cli.utils import flags
from niveshpy.cli.utils.overrides import group
from niveshpy.db.database import Database, DatabaseError
from niveshpy.cli.transaction import transactions
from niveshpy.cli.utils import output
from niveshpy.core.logging import logger


@group()
@flags.common_options
@flags.debug()
@flags.no_color()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Simple CLI command to greet the user."""
    state = ctx.ensure_object(AppState)

    output.initialize_app_state(state)

    try:
        db = Database()
        ctx.with_resource(db)
        application = Application(db)
    except DatabaseError as e:
        logger.critical(e, exc_info=True)
        ctx.exit(1)
    state.app = application


cli.add_command(transactions)
cli.add_command(securities)
cli.add_command(accounts)
cli.add_command(parse.parse)

if __name__ == "__main__":
    sys.exit(cli())

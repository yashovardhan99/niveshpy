"""Main CLI entry point for Niveshpy."""

import sys

import click

from niveshpy.cli import parse, price
from niveshpy.cli.account import accounts
from niveshpy.cli.security import securities
from niveshpy.cli.transaction import transactions
from niveshpy.cli.utils import flags, output
from niveshpy.cli.utils.overrides import group
from niveshpy.core.app import Application, AppState


@group()
@flags.common_options
@flags.debug()
@flags.no_color()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Simple CLI command to greet the user."""
    state = ctx.ensure_object(AppState)

    output.initialize_app_state(state)

    application = Application()
    state.app = application


cli.add_command(transactions)
cli.add_command(securities)
cli.add_command(accounts)
cli.add_command(parse.parse)
cli.add_command(price.prices)

if __name__ == "__main__":
    sys.exit(cli())

"""Main CLI entry point for Niveshpy."""

import sys

import click

from niveshpy.cli.utils import essentials


@essentials.group()
@click.option(
    "--debug",
    "--verbose",
    "-d",
    is_flag=True,
    help="Enable verbose logging.",
    envvar=("NIVESHPY_DEBUG", "DEBUG"),
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output.",
    envvar=("NIVESHPY_NO_COLOR", "NO_COLOR"),
)
@click.version_option(
    None, "--version", "-v", package_name="niveshpy", prog_name="NiveshPy"
)
@click.pass_context
def cli(ctx: click.Context, no_color: bool, debug: bool) -> None:
    """Simple CLI command to greet the user."""
    from niveshpy.cli.utils import output
    from niveshpy.core.app import Application, AppState

    state = ctx.ensure_object(AppState)
    state.debug = debug
    state.no_color = no_color

    output.initialize_app_state(state)

    application = Application()
    state.app = application


@essentials.group(
    cls=essentials.LazyGroup,
    import_name="niveshpy.cli.account:cli",
    parent=cli,
)
def accounts():
    """Manage accounts."""


@essentials.group(
    cls=essentials.LazyGroup,
    import_name="niveshpy.cli.security:cli",
    parent=cli,
)
def securities():
    """Work with securities."""


@essentials.group(
    cls=essentials.LazyGroup,
    import_name="niveshpy.cli.transaction:cli",
    parent=cli,
)
def transactions():
    """List, add, or delete transactions."""


@essentials.command(
    cls=essentials.LazyCommand,
    import_name="niveshpy.cli.parse:parse",
    parent=cli,
)
def parse():
    """Parse custom statements and documents.

    Parse financial documents using the specified parser and file.

    Required Args:

    \b
    * parser_key (str): The parser to use. Example: 'cas'.
    * file_path (str): Path to the file to parse.
    """  # noqa: D301


@essentials.group(
    cls=essentials.LazyGroup,
    import_name="niveshpy.cli.price:cli",
    parent=cli,
)
def prices():
    """Commands for updating and fetching price data.

    Price data for securities are stored at a daily granularity.

    External price providers can be installed to fetch price data automatically.
    """


if __name__ == "__main__":
    sys.exit(cli())

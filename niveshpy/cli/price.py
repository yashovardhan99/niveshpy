"""Update and sync market prices for securities."""

import decimal

import click

from niveshpy.cli.utils import flags, output, overrides


@overrides.group(invoke_without_command=True)
@click.pass_context
@flags.common_options
def prices(ctx: click.Context):
    """Commands for updating and fetching price data.

    Price data for securities are stored at a daily granularity.

    External price providers can be installed to fetch price data automatically.
    """
    if ctx.invoked_subcommand is None:
        ctx.forward(list_prices)


@overrides.command("list")
@click.pass_context
@flags.common_options
@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("securities", default=30)
@flags.output("format")
def list_prices(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    format: output.OutputFormat,
) -> None:
    """List latest price for all securities.

    By default, lists last available price for all securities in the portfolio.

    Optionally provide text <queries> to filter securities by key or name.
    The <queries> can also be used to provide specific dates for which prices are needed.

    Run `niveshpy prices sync` to fetch latest prices from installed providers.

    See https://yashovardhan99.github.io/niveshpy/cli/prices for example usage.
    """
    print(f"Listing prices for queries: {queries}, limit: {limit}, format: {format}")
    raise NotImplementedError


@overrides.command("update")
@click.pass_context
@flags.common_options
@click.argument("key", required=False, metavar="[<security_key>]")
@click.argument("date", required=False, metavar="[<date>]")
@click.argument(
    "ohlc", type=decimal.Decimal, required=False, nargs=-1, metavar="[<ohlc>]"
)
def update_prices(
    ctx: click.Context,
    key: str | None,
    date: str | None,
    ohlc: tuple[decimal.Decimal, ...],
):
    """Update price for a specific security.

    If run without an argument,
    interactively prompts for security and date to update the price for.

    Alternatively, provide the security <key>, <date>, and <ohlc> as arguments.

    See https://yashovardhan99.github.io/niveshpy/cli/prices for example usage and notes.
    """
    print(f"Updating price for key: {key}, date: {date}, OHLC: {ohlc}")
    raise NotImplementedError


@overrides.command("sync")
@click.pass_context
@flags.common_options
@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force update even if prices are up-to-date.",
)
@click.option(
    "--provider",
    type=str,
    help="Specify a particular price provider to use.",
)
def sync_prices(
    ctx: click.Context, queries: tuple[str, ...], force: bool, provider: str | None
) -> None:
    """Sync prices from installed providers.

    By default, syncs prices for all securities in the portfolio.

    Optionally provide text <queries> to filter securities or specific dates to sync prices for.

    See https://yashovardhan99.github.io/niveshpy/cli/prices for example usage.
    """
    print(
        f"Syncing prices for queries: {queries}, force: {force}, provider: {provider}"
    )
    raise NotImplementedError


prices.add_command(list_prices, name="list")
prices.add_command(update_prices, name="update")
prices.add_command(sync_prices, name="sync")

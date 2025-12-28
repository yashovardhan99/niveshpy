"""Update and sync market prices for securities."""

import datetime
import decimal
from collections.abc import MutableMapping

import click
import rich
import rich.progress

import niveshpy.models.output
from niveshpy.cli.utils import flags, output, overrides
from niveshpy.core import providers as provider_registry
from niveshpy.core.app import AppState
from niveshpy.exceptions import NiveshPySystemError, NiveshPyUserError
from niveshpy.models.price import PriceDataRead
from niveshpy.services.result import MergeAction


class ProviderType(click.ParamType):
    """Custom Click parameter type for selecting a provider."""

    name = "provider"

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ):
        """Provide shell completion for provider names."""
        if provider_registry.is_empty():
            provider_registry.discover_installed_providers()
        return [
            click.shell_completion.CompletionItem(
                key, help=factory.get_provider_info().name
            )
            for key, factory in provider_registry.list_providers_starting_with(
                incomplete
            )
        ]


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
    state = ctx.ensure_object(AppState)
    with output.loading_spinner("Loading prices..."):
        result = state.app.price.list_prices(queries=queries, limit=limit)
    if result.total == 0:
        msg = (
            "No prices "
            + ("match your query." if queries else "found in the database.")
            + " Try syncing prices using 'niveshpy prices sync'."
        )
        output.display_warning(msg)
    else:
        output.display_dataframe(
            result.data,
            format,
            PriceDataRead.rich_format_map(),
            extra_message=f"Showing {limit:,} of {result.total:,} prices."
            if result.total > limit
            else None,
        )


@overrides.command("update")
@click.pass_context
@flags.common_options
@click.argument("key", required=True, metavar="[<security_key>]")
@click.argument(
    "date", required=True, metavar="[<date>]", type=click.DateTime(formats=["%Y-%m-%d"])
)
@click.argument(
    "ohlc", type=decimal.Decimal, required=True, nargs=-1, metavar="[<ohlc>]"
)
def update_prices(
    ctx: click.Context,
    key: str,
    date: datetime.date,
    ohlc: tuple[decimal.Decimal, ...],
):
    """Update price for a specific security.

    Requires the security <key>, <date>, and <ohlc> as arguments.

    See https://yashovardhan99.github.io/niveshpy/cli/prices for example usage and notes.
    """
    if len(ohlc) not in (1, 2, 4):
        raise NiveshPyUserError(
            "Invalid number of OHLC values provided. Provide 1 (close), "
            "2 (open, close), or 4 (open, high, low, close) values."
        )
    state = ctx.ensure_object(AppState)
    result = state.app.price.update_price(key, date, ohlc, source="cli")

    action = "added" if result == MergeAction.INSERT else "updated"
    output.display_success(f"Price was {action} successfully.")


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
    type=ProviderType(),
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
    state = ctx.ensure_object(AppState)

    progress_bar = output.get_progress_bar()
    progress_tasks: MutableMapping[str, rich.progress.TaskID] = {}

    # Validate provider key (if provided)
    if provider is not None:
        state.app.price.validate_provider(provider)

    # Start sync process

    with progress_bar:
        for message in state.app.price.sync_prices(
            queries=queries, force=force, provider_key=provider
        ):
            if isinstance(message, niveshpy.models.output.ProgressUpdate):
                output.update_progress_bar(progress_bar, progress_tasks, message)
            elif isinstance(message, niveshpy.models.output.BaseMessage):
                output.handle_niveshpy_message(message, console=progress_bar.console)
            else:
                raise NiveshPySystemError(
                    "Unexpected message type received during price sync.",
                    f"Received unknown message type: {type(message).__name__}.",
                    message,
                )


prices.add_command(list_prices, name="list")
prices.add_command(update_prices, name="update")
prices.add_command(sync_prices, name="sync")

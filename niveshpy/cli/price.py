"""Update and sync market prices for securities."""

import datetime
import decimal
from collections.abc import MutableMapping

import click
import click.shell_completion
import rich
import rich.progress

import niveshpy.models.output
from niveshpy.cli.utils import essentials, flags, output, overrides
from niveshpy.core import providers as provider_registry
from niveshpy.core.app import AppState
from niveshpy.exceptions import InvalidInputError
from niveshpy.models.price import (
    PriceDisplay,
    PricePublic,
    PricePublicWithRelations,
)
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


@essentials.group()
def cli():
    """Wrapper group for price-related commands."""


@overrides.command("list")
@click.pass_context
@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("securities", default=30)
@flags.offset("securities", default=0)
@flags.output("format")
def list_prices(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    offset: int,
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
        result = state.app.price.list_prices(
            queries=queries, limit=limit, offset=offset
        )
    if len(result) == 0:
        msg = (
            "No prices "
            + ("match your query." if queries else "found in the database.")
            + " Try syncing prices using 'niveshpy prices sync'."
        )
        output.display_warning(msg)
    else:
        fmt_cls = (
            PricePublicWithRelations
            if format == output.OutputFormat.JSON
            else (PricePublic if format == output.OutputFormat.CSV else PriceDisplay)
        )

        prices = [fmt_cls.model_validate(price) for price in result]
        output.display_list(
            fmt_cls,
            prices,
            format,
            extra_message=f"Showing first {limit:,} prices."
            if len(result) == limit and offset == 0
            else (
                f"Showing prices {offset + 1:,} to {offset + len(result):,}."
                if offset > 0
                else None
            ),
        )


@overrides.command("update")
@click.pass_context
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
        raise InvalidInputError(
            ohlc,
            "Invalid number of OHLC values provided. Provide 1 (close), "
            "2 (open, close), or 4 (open, high, low, close) values.",
        )
    state = ctx.ensure_object(AppState)
    result = state.app.price.update_price(key, date, ohlc, source="cli")

    action = "added" if result == MergeAction.INSERT else "updated"
    output.display_success(f"Price was {action} successfully.")


@overrides.command("sync")
@click.pass_context
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
            else:
                output.handle_niveshpy_message(message, console=progress_bar.console)


cli.add_command(list_prices, name="list")
cli.add_command(update_prices, name="update")
cli.add_command(sync_prices, name="sync")

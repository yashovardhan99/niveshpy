"""Update and sync market prices for securities."""

import datetime
import decimal
import json
from collections.abc import MutableMapping
from pathlib import Path

import click
import click.shell_completion

from niveshpy.cli.models.price import PriceDisplay
from niveshpy.cli.utils import essentials, flags, overrides
from niveshpy.cli.utils.builders import build_csv, build_table
from niveshpy.cli.utils.display import (
    capture_for_pager,
    display,
    display_json,
    display_success,
    display_warning,
    loading_spinner,
)
from niveshpy.cli.utils.models import OutputFormat
from niveshpy.core.app import AppState
from niveshpy.core.converter import get_csv_converter, get_json_converter
from niveshpy.exceptions import InvalidInputError


class ProviderType(click.ParamType):
    """Custom Click parameter type for selecting a provider."""

    name = "provider"

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ):
        """Provide shell completion for provider names."""
        from niveshpy.core import providers as provider_registry

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
@flags.output_file()
def list_prices(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: OutputFormat,
    output_file: Path | None,
) -> None:
    """List latest price for all securities.

    By default, lists last available price for all securities in the portfolio.

    Optionally provide text <queries> to filter securities by key or name.
    The <queries> can also be used to provide specific dates for which prices are needed.

    Run `niveshpy prices sync` to fetch latest prices from installed providers.

    See https://yashovardhan99.github.io/niveshpy/cli/prices for example usage.
    """
    state = ctx.ensure_object(AppState)
    with loading_spinner("Loading prices..."):
        result = state.app.price.list_prices(
            queries=queries, limit=limit, offset=offset
        )
    if len(result) == 0:
        msg = (
            "No prices "
            + ("match your query." if queries else "found in the database.")
            + " Try syncing prices using 'niveshpy prices sync'."
        )
        display_warning(msg)
        ctx.exit()
    prices = map(PriceDisplay.from_domain, result)
    extra_message = (
        f"Showing first {limit:,} prices."
        if len(result) == limit and offset == 0
        else (
            f"Showing prices {offset + 1:,} to {offset + len(result):,}."
            if offset > 0
            else None
        )
    )

    with capture_for_pager(enabled=output_file is None or format == OutputFormat.TABLE):
        if format == OutputFormat.TABLE:
            table = build_table(prices, PriceDisplay.columns)
            if output_file:
                display_warning(
                    "Output file specified, but table format does not support file output. Ignoring --output-file flag."
                )
            display(table)
            if extra_message:
                display(extra_message)
        elif format == OutputFormat.CSV:
            c = get_csv_converter()
            csv = build_csv(
                c.unstructure(result),
                fields=PriceDisplay.csv_fields,
                output_file=output_file,
            )
            if csv:
                display(csv)
        elif format == OutputFormat.JSON:
            c = get_json_converter()
            data = c.unstructure(result)
            if output_file:
                with output_file.open("w") as f:
                    json.dump(data, f, indent=4)
            else:
                display_json(data=data)


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
    state.app.price.update_price(key, date, ohlc, source="cli")

    display_success("Price was saved successfully.")


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
    import rich.progress

    from niveshpy.cli.utils import output
    from niveshpy.models.output import ProgressUpdate

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
            if isinstance(message, ProgressUpdate):
                output.update_progress_bar(progress_bar, progress_tasks, message)
            else:
                output.handle_niveshpy_message(message, console=progress_bar.console)


cli.add_command(list_prices, name="list")
cli.add_command(update_prices, name="update")
cli.add_command(sync_prices, name="sync")

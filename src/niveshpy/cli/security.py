"""CLI commands for managing securities."""

import json
from pathlib import Path
from textwrap import dedent

import click

from niveshpy.cli.utils import essentials, flags
from niveshpy.cli.utils.builders import build_csv, build_table
from niveshpy.cli.utils.display import (
    capture_for_pager,
    display,
    display_error,
    display_json,
    display_success,
    display_warning,
    loading_spinner,
)
from niveshpy.cli.utils.formatters import (
    format_datetime,
    format_security_category,
    format_security_type,
)
from niveshpy.cli.utils.models import Column, OutputFormat
from niveshpy.cli.utils.overrides import command
from niveshpy.core.app import AppState
from niveshpy.core.converter import get_csv_converter, get_json_converter
from niveshpy.core.logging import logger
from niveshpy.exceptions import InvalidInputError, ResourceNotFoundError
from niveshpy.models.security import (
    SecurityCategory,
    SecurityType,
)


@essentials.group()
def cli() -> None:
    """Wrapper group for security-related commands."""


@command("list")
@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("securities", default=30)
@flags.offset("securities", default=0)
@flags.output("format")
@flags.output_file()
@click.pass_context
def show(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: OutputFormat,
    output_file: Path | None,
) -> None:
    """List all securities.

    Optionally provide a text QUERY to filter securities by key or name.
    """
    state = ctx.ensure_object(AppState)
    with loading_spinner("Loading securities..."):
        result = state.app.security.list_securities(
            queries=queries, limit=limit, offset=offset
        )

    if len(result) == 0:
        msg = "No securities " + (
            "match your query." if queries else "found in the database."
        )
        display_warning(msg)
        ctx.exit()

    extra_message = (
        f"Showing first {limit:,} securities."
        if len(result) == limit and offset == 0
        else (
            f"Showing securities {offset + 1:,} to {offset + len(result):,}."
            if offset > 0
            else None
        )
    )
    with capture_for_pager(enabled=output_file is None or format == OutputFormat.TABLE):
        if format == OutputFormat.TABLE:
            if extra_message:
                display(extra_message)

            if output_file:
                display_warning(
                    "Output file specified, but table format does not support file output. Ignoring --output-file flag."
                )

            columns = [
                Column("key", style="green", justify="right"),
                Column("name"),
                Column("type", formatter=format_security_type),
                Column("category", formatter=format_security_category),
                Column("created", style="dim", formatter=format_datetime),
                Column("source", style="dim"),
            ]

            table = build_table(result, columns)
            display(table)
        elif format == OutputFormat.CSV:
            c = get_csv_converter()
            csv = build_csv(
                c.unstructure(result),
                fields=["key", "name", "type", "category", "created", "source"],
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


@command()
@click.argument("default_key", metavar="[<key>]", default="")
@click.argument("default_name", metavar="[<name>]", default="")
@click.argument(
    "default_category",
    required=False,
    type=click.Choice(SecurityCategory, case_sensitive=False),
    metavar="[<category>]",
)
@click.argument(
    "default_type",
    required=False,
    type=click.Choice(SecurityType, case_sensitive=False),
    metavar="[<type>]",
)
@flags.no_input()
@click.pass_context
def add(
    ctx: click.Context,
    default_key: str = "",
    default_name: str = "",
    default_category: str | None = None,
    default_type: str | None = None,
) -> None:
    """Add a new security.

    To create securities interactively, run the command with no arguments.
    To add a single security non-interactively, provide all arguments along with --no-input.

    <key> is a unique identifier for the security, e.g., ticker symbol or ISIN. If another
    security with the same key exists, no action will be taken.

    category and type should be one of the enum values:

    \b
    * Category: EQUITY, DEBT, COMMODITY, OTHER
    * Type: STOCK, BOND, MUTUAL_FUND, ETF, OTHER
    """  # noqa: D301
    from InquirerPy import get_style, inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.validator import EmptyInputValidator

    state = ctx.ensure_object(AppState)

    if state.no_input:
        # Non-interactive mode: all arguments must be provided
        if not (default_key and default_name and default_category and default_type):
            raise InvalidInputError(
                (default_key, default_name, default_category, default_type),
                "When running in non-interactive mode, all arguments for adding a security must be provided.",
            )

        result = state.app.security.add_security(
            default_key.strip(),
            default_name.strip(),
            SecurityType(default_type.strip().lower()),
            SecurityCategory(default_category.strip().lower()),
            source="cli",
        )

        if not result:
            display_warning(
                f"Security with key '{default_key}' already exists. No changes were made."
            )
        else:
            display_success("Security was added successfully.")
        return

    display("Adding a new security.")
    display(
        dedent(
            """
            Any command-line arguments will be used as defaults.
            Use arrow keys to navigate, and [i]Enter[/i] to accept defaults.
            Use [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.
        """
        )
    )
    inquirer_style = get_style({}, style_override=state.no_color)

    while True:
        # Interactive mode: prompt for each field
        security_key: str = (
            inquirer.text(
                message="Security Key",
                instruction="(A unique identifier for the security, e.g., ticker symbol or ISIN)",
                long_instruction="If another security with the same key exists, it will be ignored.",
                validate=EmptyInputValidator(),
                default=default_key,
                style=inquirer_style,
            )
            .execute()
            .strip()
        )
        name: str = (
            inquirer.text(
                message="Security Name",
                instruction="(The full name of the security)",
                validate=EmptyInputValidator(),
                default=default_name,
                style=inquirer_style,
            )
            .execute()
            .strip()
        )
        category: SecurityCategory = inquirer.select(
            message="Security Category",
            choices=[Choice(cat, name=cat.name) for cat in SecurityCategory],
            default=default_category,
            style=inquirer_style,
        ).execute()
        security_type: SecurityType = inquirer.select(
            message="Security Type",
            choices=[Choice(t, name=t.name) for t in SecurityType],
            default=default_type,
            style=inquirer_style,
        ).execute()

        # Add the security
        with loading_spinner(f"Adding security '{name}'..."):
            result = state.app.security.add_security(
                security_key,
                name,
                security_type,
                category,
                source="cli",
            )

        if not result:
            display_warning(
                f"Security with key '{security_key}' already exists. No changes were made."
            )
        else:
            display_success("Security was added successfully.")

        if default_key:
            # If defaults were provided via command-line arguments, exit after one iteration
            break

        display("Add Next Security")
        display("Press [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.")


@command()
@click.argument("queries", required=False, metavar="[<queries>]", default=(), nargs=-1)
@flags.limit("limit", default=100)
@flags.no_input()
@flags.force()
@flags.dry_run()
@click.pass_context
def delete(
    ctx: click.Context, queries: tuple[str, ...], limit: int, force: bool, dry_run: bool
) -> None:
    """Delete a security based on a query.

    If no key is provided, you will be prompted to select from existing securities.
    The query will be used to search for securities by key or name.
    If multiple securities match the provided query, you will be prompted to select one.

    Associated transactions and holdings are not deleted but will no longer be visible in reports.

    When running in a non-interactive mode, --force must be provided to confirm deletion. Additionally, the <query> must match exactly one security key.
    """
    from InquirerPy import get_style, inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.validator import EmptyInputValidator

    state = ctx.ensure_object(AppState)

    if state.no_input and not force:
        display_error(
            "When running in non-interactive mode, --force must be provided to confirm deletion."
        )
        ctx.exit(1)

    inquirer_style = get_style({}, style_override=state.no_color)

    candidates = state.app.security.resolve_security_key(
        queries, limit, allow_ambiguous=not state.no_input
    )

    if not candidates:
        raise ResourceNotFoundError("security", " ".join(queries))
    elif len(candidates) > 1:
        choices: list[Choice] = [
            Choice(sec.key, name=f"{sec.key} - {sec.name}") for sec in candidates
        ]
        security_key = inquirer.fuzzy(
            message="Multiple securities found. Select one to delete:",
            choices=choices,
            validate=EmptyInputValidator(),
            style=inquirer_style,
        ).execute()
        security = state.app.security.resolve_security_key((security_key,), 1, False)[0]
    else:
        security = candidates[0]

    if dry_run or not force:
        display("You have selected the following security:", security)
        if (
            not dry_run
            and not inquirer.confirm(
                "Are you sure you want to delete this security?",
                default=False,
                style=inquirer_style,
            ).execute()
        ):
            logger.info("Security deletion aborted by user.")
            ctx.abort()

    if dry_run:
        display("Dry Run: No changes were made.")
        ctx.exit()

    with loading_spinner(f"Deleting security '{security.key}'..."):
        deleted = state.app.security.delete_security(security.key)
        if deleted:
            display_success(
                f"Security '{security.key}' was deleted successfully.",
            )
        else:
            display_warning(
                f"Security with key '{security.key}' was not found. No changes were made."
            )


cli.add_command(show)
cli.add_command(add)
cli.add_command(delete, name="delete")

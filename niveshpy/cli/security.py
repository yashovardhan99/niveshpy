"""CLI commands for managing securities."""

from collections.abc import Sequence
from textwrap import dedent

import click
from InquirerPy import get_style, inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import EmptyInputValidator

from niveshpy.cli.utils import essentials, flags, output
from niveshpy.cli.utils.overrides import command
from niveshpy.core.app import AppState
from niveshpy.core.logging import logger
from niveshpy.exceptions import InvalidInputError, OperationError, ResourceNotFoundError
from niveshpy.models.security import (
    Security,
    SecurityCategory,
    SecurityType,
)
from niveshpy.services.result import MergeAction


@essentials.group()
def cli() -> None:
    """Wrapper group for security-related commands."""


@command("list")
@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("securities", default=30)
@flags.offset("securities", default=0)
@flags.output("format")
@click.pass_context
def show(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: output.OutputFormat,
) -> None:
    """List all securities.

    Optionally provide a text QUERY to filter securities by key or name.
    """
    state = ctx.ensure_object(AppState)
    with output.loading_spinner("Loading securities..."):
        securities = state.app.security.list_securities(
            queries=queries, limit=limit, offset=offset
        )

    if len(securities) == 0:
        output.display_warning(
            "No securities "
            + ("match your query." if queries else "found in the database.")
        )
    else:
        output.display_list(
            Security,
            securities,
            format,
            extra_message=f"Showing first {limit:,} securities."
            if len(securities) == limit and offset == 0
            else (
                f"Showing securities {offset + 1:,} to {offset + len(securities):,}."
                if offset > 0
                else None
            ),
        )


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
    security with the same key exists, it will be updated.

    category and type should be one of the enum values:

    \b
    * Category: EQUITY, DEBT, COMMODITY, OTHER
    * Type: STOCK, BOND, MUTUAL_FUND, ETF, OTHER
    """  # noqa: D301
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

        action = "added" if result.action == MergeAction.INSERT else "updated"
        output.display_success(
            f"Security '{result.data.name}' was {action} successfully."
        )
        return

    output.display_message("Adding a new security.")
    output.display_message(
        dedent("""
            Any command-line arguments will be used as defaults.
            Use arrow keys to navigate, and [i]Enter[/i] to accept defaults.
            Use [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.
        """)
    )
    inquirer_style = get_style({}, style_override=state.no_color)

    while True:
        # Interactive mode: prompt for each field
        security_key: str = (
            inquirer.text(
                message="Security Key",
                instruction="(A unique identifier for the security, e.g., ticker symbol or ISIN)",
                long_instruction="If another security with the same key exists, it will be updated.",
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
        with output.loading_spinner(f"Adding security '{name}'..."):
            result = state.app.security.add_security(
                security_key,
                name,
                security_type,
                category,
                source="cli",
            )

        action = "added" if result.action == MergeAction.INSERT else "updated"
        output.display_success(
            f"Security '{result.data.name}' was {action} successfully."
        )

        if default_key:
            # If defaults were provided via command-line arguments, exit after one iteration
            break

        output.display_message("Add Next Security")
        output.display_message("Press [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.")


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
    state = ctx.ensure_object(AppState)

    if state.no_input and not force:
        output.display_error(
            "When running in non-interactive mode, --force must be provided to confirm deletion."
        )
        ctx.exit(1)

    inquirer_style = get_style({}, style_override=state.no_color)

    candidates: Sequence[Security] = state.app.security.resolve_security_key(
        queries, limit, allow_ambiguous=not state.no_input
    )

    security: Security

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
        output.display_message("You have selected the following security:", security)
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
        output.display_message("Dry Run: No changes were made.")
        ctx.exit()

    with output.loading_spinner(f"Deleting security '{security.key}'..."):
        deleted = state.app.security.delete_security(security.key)
        if deleted:
            output.display_success(
                f"Security '{security.key}' was deleted successfully.",
            )
        else:
            msg = f"Security '{security.key}' could not be deleted."
            raise OperationError(msg)


cli.add_command(show)
cli.add_command(add)
cli.add_command(delete, name="delete")

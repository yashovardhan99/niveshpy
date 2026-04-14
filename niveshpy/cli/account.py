"""CLI commands for managing accounts."""

import json
from pathlib import Path

import click

from niveshpy.cli.models.account import AccountDisplay
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
from niveshpy.cli.utils.models import OutputFormat
from niveshpy.cli.utils.overrides import command
from niveshpy.core.app import AppState
from niveshpy.core.logging import logger
from niveshpy.exceptions import (
    OperationError,
    ResourceError,
    ResourceNotFoundError,
)
from niveshpy.services.result import MergeAction


@essentials.group()
def cli() -> None:
    """Wrapper group for account-related commands."""


@command("list")
@click.argument("queries", default=(), required=False, nargs=-1, metavar="[<queries>]")
@flags.limit("accounts", default=30)
@flags.offset("accounts", default=0)
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
    """List all accounts.

    An optional QUERY can be provided to filter accounts by name or institution.
    """
    state = ctx.ensure_object(AppState)
    with loading_spinner("Loading accounts..."):
        result = state.app.account.list_accounts(
            queries=queries, limit=limit, offset=offset
        )

        if len(result) == 0:
            msg = "No accounts " + (
                "match your queries." if queries else "found in the database."
            )
            display_warning(msg)
            ctx.exit()

    accounts = map(AccountDisplay.from_domain, result)
    extra_message = (
        f"Showing first {limit:,} accounts."
        if len(result) == limit and offset == 0
        else (
            f"Showing accounts {offset + 1:,} to {offset + len(result):,}."
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

            table = build_table(accounts, AccountDisplay.columns)
            display(table)
        elif format == OutputFormat.CSV:
            csv = build_csv(
                map(AccountDisplay.to_csv_dict, accounts),
                fields=AccountDisplay.csv_fields,
                output_file=output_file,
            )
            if csv:
                display(csv)
        elif format == OutputFormat.JSON:
            data = [acc.to_json_dict() for acc in accounts]
            if output_file:
                with output_file.open("w") as f:
                    json.dump(data, f, indent=4)
            else:
                display_json(data=data)


@command()
@click.argument("name", metavar="[<name>]", default="")
@click.argument("institution", metavar="[<institution>]", default="")
@flags.no_input()
@click.pass_context
def add(ctx: click.Context, name: str, institution: str) -> None:
    """Add a new account.

    To add accounts interactively, run the command without any arguments.
    To add a single account non-interactively, provide the account name and institution using `niveshpy account add <name> <institution>`.

    <name> and <institution> are used to uniquely identify the account. If an account with the same name and institution already exists, it will not be added again.
    """
    from InquirerPy import get_style, inquirer
    from InquirerPy.validator import EmptyInputValidator

    state = ctx.ensure_object(AppState)

    if state.no_input:
        # Non-interactive mode
        if not name or not institution:
            display_error(
                "Account name and institution must be provided in non-interactive mode."
            )
            ctx.exit(1)

        result = state.app.account.add_account(
            name=name, institution=institution, source="cli"
        )
        if result.action == MergeAction.NOTHING:
            display_warning(f"Account already exists with ID {result.data}.")
        else:
            display_success(
                f"Account [b]{name}[/b] added successfully with ID {result.data}."
            )
    else:
        # Interactive mode

        inquirer_style = get_style({}, style_override=state.no_color)

        while True:
            display("Use [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.")
            name = (
                inquirer.text(
                    message="Account Name:",
                    validate=EmptyInputValidator(),
                    style=inquirer_style,
                    default=name,
                )
                .execute()
                .strip()
            )
            institution = (
                inquirer.text(
                    message="Institution Name:",
                    validate=EmptyInputValidator(),
                    style=inquirer_style,
                    default=institution,
                )
                .execute()
                .strip()
            )

            result = state.app.account.add_account(
                name=name, institution=institution, source="cli"
            )
            if result.action == MergeAction.NOTHING:
                display_warning(f"Account already exists with ID {result.data}.")
            else:
                display_success(
                    f"Account [b]{name}[/b] added successfully with ID {result.data}."
                )

            # Reset for next iteration
            name = ""
            institution = ""


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
    """Delete an account based on a query.

    If no ID is provided, you will be prompted to select from existing accounts.
    The query will first attempt to match an account by its unique ID. If no exact match is found, it will search by name and institution.
    If multiple accounts match the provided query, you will be prompted to select one.

    Associated transactions and holdings are not deleted but might no longer be visible in some reports.

    When running in a non-interactive mode, --force must be provided to confirm deletion. Additionally, the <query> must match exactly one account ID.
    """
    from InquirerPy import get_style, inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.validator import NumberValidator

    state = ctx.ensure_object(AppState)

    if state.no_input and not force:
        display_error(
            "When running in non-interactive mode, --force must be provided to confirm deletion."
        )
        ctx.exit(1)

    inquirer_style = get_style({}, style_override=state.no_color)

    candidates = state.app.account.resolve_account_id(
        queries, limit, allow_ambiguous=not state.no_input
    )

    if not candidates:
        raise ResourceNotFoundError("account", " ".join(queries))
    elif len(candidates) > 1:
        choices: list[Choice] = [
            Choice(acc.id, name=f"[{acc.id}] {acc.name} ({acc.institution})")
            for acc in candidates
        ]
        account_id = inquirer.fuzzy(
            message="Multiple accounts found. Select one to delete:",
            choices=choices,
            validate=NumberValidator(),
            style=inquirer_style,
        ).execute()

        account = state.app.account.resolve_account_id((str(account_id),), 1, False)[0]
    else:
        account = candidates[0]
    if dry_run or not force:
        display("The following account will be deleted: ", account)
        if (
            not dry_run
            and not inquirer.confirm(
                "Are you sure you want to delete this account?",
                default=False,
                style=inquirer_style,
            ).execute()
        ):
            logger.info("Account deletion aborted by user.")
            ctx.abort()

    if dry_run:
        display("Dry Run: No changes were made.")
        ctx.exit()

    with loading_spinner(f"Deleting account with ID {account.id}..."):
        if account.id is None:
            raise ResourceError("Account ID is missing, cannot proceed with deletion.")
        deleted = state.app.account.delete_account(account.id)
        if deleted:
            display_success(f"Account ID {account.id} was deleted successfully.")
        else:
            msg = f"Account ID {account.id} could not be deleted."
            raise OperationError(msg)


cli.add_command(show)
cli.add_command(add)
cli.add_command(delete)

"""CLI commands for managing accounts."""

from collections.abc import Sequence

import click
import InquirerPy
import InquirerPy.inquirer
import InquirerPy.validator
from InquirerPy.base.control import Choice

from niveshpy.cli.utils import essentials, flags, output
from niveshpy.cli.utils.overrides import command
from niveshpy.core.app import AppState
from niveshpy.core.logging import logger
from niveshpy.exceptions import (
    OperationError,
    ResourceNotFoundError,
)
from niveshpy.models.account import AccountPublic
from niveshpy.services.result import MergeAction


@essentials.group()
def cli() -> None:
    """Wrapper group for account-related commands."""


@command("list")
@click.argument("queries", default=(), required=False, nargs=-1, metavar="[<queries>]")
@flags.limit("accounts", default=30)
@flags.offset("accounts", default=0)
@flags.output("format")
@click.pass_context
def show(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: output.OutputFormat,
) -> None:
    """List all accounts.

    An optional QUERY can be provided to filter accounts by name or institution.
    """
    state = ctx.ensure_object(AppState)
    with output.loading_spinner("Loading accounts..."):
        result = state.app.account.list_accounts(
            queries=queries, limit=limit, offset=offset
        )

        if len(result) == 0:
            msg = "No accounts " + (
                "match your queries." if queries else "found in the database."
            )
            output.display_warning(msg)
            ctx.exit()

    output.display_list(
        AccountPublic,
        result,
        format,
        extra_message=f"Showing first {limit:,} accounts."
        if len(result) == limit and offset == 0
        else (
            f"Showing accounts {offset + 1:,} to {offset + len(result):,}."
            if offset > 0
            else None
        ),
    )


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
    state = ctx.ensure_object(AppState)

    if state.no_input:
        # Non-interactive mode
        if not name or not institution:
            output.display_error(
                "Account name and institution must be provided in non-interactive mode."
            )
            ctx.exit(1)

        result = state.app.account.add_account(
            name=name, institution=institution, source="cli"
        )
        if result.action == MergeAction.NOTHING:
            output.display_warning(f"Account already exists with ID {result.data.id}.")
        else:
            output.display_success(
                f"Account [b]{name}[/b] added successfully with ID {result.data.id}."
            )
    else:
        # Interactive mode

        inquirer_style = InquirerPy.get_style({}, style_override=state.no_color)

        while True:
            output.display_message("Use [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.")
            name = (
                InquirerPy.inquirer.text(
                    message="Account Name:",
                    validate=InquirerPy.validator.EmptyInputValidator(),
                    style=inquirer_style,
                    default=name,
                )
                .execute()
                .strip()
            )
            institution = (
                InquirerPy.inquirer.text(
                    message="Institution Name:",
                    validate=InquirerPy.validator.EmptyInputValidator(),
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
                output.display_warning(
                    f"Account already exists with ID {result.data.id}."
                )
            else:
                output.display_success(
                    f"Account [b]{name}[/b] added successfully with ID {result.data.id}."
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
    state = ctx.ensure_object(AppState)

    if state.no_input and not force:
        output.display_error(
            "When running in non-interactive mode, --force must be provided to confirm deletion."
        )
        ctx.exit(1)

    inquirer_style = InquirerPy.get_style({}, style_override=state.no_color)

    candidates: Sequence[AccountPublic] = state.app.account.resolve_account_id(
        queries, limit, allow_ambiguous=not state.no_input
    )

    account: AccountPublic

    if not candidates:
        raise ResourceNotFoundError("account", " ".join(queries))
    elif len(candidates) > 1:
        choices: list[Choice] = [
            Choice(acc.id, name=f"[{acc.id}] {acc.name} ({acc.institution})")
            for acc in candidates
        ]
        account_id = InquirerPy.inquirer.fuzzy(
            message="Multiple accounts found. Select one to delete:",
            choices=choices,
            validate=InquirerPy.validator.NumberValidator(),
            style=inquirer_style,
        ).execute()

        account = state.app.account.resolve_account_id((str(account_id),), 1, False)[0]
    else:
        account = candidates[0]
    if dry_run or not force:
        output.display_message("The following account will be deleted: ", account)
        if (
            not dry_run
            and not InquirerPy.inquirer.confirm(
                "Are you sure you want to delete this account?",
                default=False,
                style=inquirer_style,
            ).execute()
        ):
            logger.info("Account deletion aborted by user.")
            ctx.abort()

    if dry_run:
        output.display_message("Dry Run: No changes were made.")
        ctx.exit()

    with output.loading_spinner(f"Deleting account with ID {account.id}..."):
        deleted = state.app.account.delete_account(account.id)
        if deleted:
            output.display_success(f"Account ID {account.id} was deleted successfully.")
        else:
            msg = f"Account ID {account.id} could not be deleted."
            raise OperationError(msg)


cli.add_command(show)
cli.add_command(add)
cli.add_command(delete)

"""CLI commands for managing accounts."""

import click
import InquirerPy
import InquirerPy.inquirer
import InquirerPy.validator

from niveshpy.cli.utils import flags, output
from niveshpy.cli.utils.overrides import command, group
from niveshpy.core.app import AppState
from niveshpy.core.logging import logger
from niveshpy.db.database import DatabaseError
from niveshpy.models.account import Account
from niveshpy.services.result import MergeAction, ResolutionStatus


@group(invoke_without_command=True)
@click.pass_context
def accounts(ctx: click.Context) -> None:
    """Manage accounts."""
    if ctx.invoked_subcommand is None:
        ctx.forward(show)


@command("list")
@click.argument("queries", default=(), required=False, nargs=-1, metavar="[<queries>]")
@flags.limit("accounts", default=30)
@flags.offset("accounts", default=0)
@flags.output("format")
@flags.common_options
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
        try:
            result = state.app.account_v2.list_accounts(
                queries=queries, limit=limit, offset=offset
            )
        except ValueError as e:
            logger.error(e, exc_info=True)
            ctx.exit(1)
        except DatabaseError as e:
            logger.critical(e, exc_info=True)
            ctx.exit(1)

        if len(result) == 0:
            msg = "No accounts " + (
                "match your queries." if queries else "found in the database."
            )
            output.display_warning(msg)
            ctx.exit()

    output.display_list(
        Account,
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
@flags.common_options
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

        try:
            result = state.app.account_v2.add_account(
                name=name, institution=institution, source="cli"
            )
        except ValueError as e:
            output.display_error(str(e))
            ctx.exit(1)
        except RuntimeError as e:
            output.display_error(str(e))
            ctx.exit(1)
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

            try:
                result = state.app.account_v2.add_account(
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
            except ValueError as e:
                logger.error(e)
                continue
            except RuntimeError as e:
                logger.error(e)
                continue
            except DatabaseError as e:
                logger.critical(e, exc_info=True)
                ctx.exit(1)


@command()
@click.argument("queries", required=False, metavar="[<queries>]", default=(), nargs=-1)
@flags.limit("limit", default=100)
@flags.no_input()
@flags.force()
@flags.dry_run()
@flags.common_options
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

    resolution = state.app.account.resolve_account_id(
        queries, limit, allow_ambiguous=not state.no_input
    )

    if resolution.status == ResolutionStatus.NOT_FOUND:
        output.display_error(
            "No accounts found matching the provided query. If running in non-interactive mode, ensure the query matches an account ID exactly."
        )
        ctx.exit(1)
    elif resolution.status == ResolutionStatus.EXACT:
        account = resolution.exact
        if account is None:
            logger.error(
                "Account resolution failed unexpectedly. Please report this bug."
            )
            logger.debug("Resolution object: %s", resolution)
            ctx.exit(1)

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

    elif resolution.status == ResolutionStatus.AMBIGUOUS:
        if state.no_input or not resolution.candidates:
            output.display_error(
                "The provided query is ambiguous and may match multiple accounts. Please refine your query."
            )
            ctx.exit(1)

        choices = [
            InquirerPy.base.control.Choice(
                acc.id, name=f"[{acc.id}] {acc.name} ({acc.institution})"
            )
            for acc in resolution.candidates
        ]
        account_id = InquirerPy.inquirer.fuzzy(
            message="Multiple accounts found. Select one to delete:",
            choices=choices,
            validate=InquirerPy.validator.NumberValidator(),
            style=inquirer_style,
        ).execute()

        account = state.app.account.resolve_account_id(
            (str(account_id),), 1, False
        ).exact
        if account is None:
            logger.error(
                "Selected account could not be found. It may have been deleted already."
            )
            logger.debug("Resolution object: %s", resolution)
            ctx.exit(1)

        if not force:
            output.display_message("You have selected the following account:", account)
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
            logger.error(
                "Failed to delete account %s. It may have already been deleted.",
                account.id,
            )
            logger.debug("Resolution object: %s", resolution)


accounts.add_command(show)
accounts.add_command(add)
accounts.add_command(delete)

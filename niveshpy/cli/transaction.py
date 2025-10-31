"""CLI API for transactions."""

import datetime
import decimal
import textwrap
import click
from niveshpy.cli.utils import flags, inputs
from niveshpy.cli.utils.overrides import command, group
from niveshpy.core.app import AppState
from niveshpy.db.database import DatabaseError
from niveshpy.models.transaction import (
    TransactionRead,
    TransactionType,
)
from niveshpy.cli.utils import output
from niveshpy.core.logging import logger
from InquirerPy import inquirer, validator, get_style
from InquirerPy.base import control

from niveshpy.services.result import ResolutionStatus


@group(invoke_without_command=True)
@flags.common_options
@click.pass_context
def transactions(ctx: click.Context) -> None:
    """List, add, or delete transactions."""
    if ctx.invoked_subcommand is None:
        ctx.forward(show)


@command("list")
@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("accounts", default=30)
@flags.output("format")
@flags.common_options
@click.pass_context
def show(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    format: output.OutputFormat,
) -> None:
    """List all transactions.

    Optionally provide a text QUERY to filter transactions by various attributes.

    Examples:
        niveshpy transactions
        niveshpy transactions list gold # Filter by a security with 'gold' in its name or key
        niveshpy transactions list acct:Z123 # Filter by account 'Z123'
        niveshpy transactions list type:purchase # Filter by transaction type 'purchase'

    View the documentation at https://yashovardhan99.github.io/niveshpy/cli/queries/ for more details on query syntax.
    """
    state = ctx.ensure_object(AppState)
    with output.loading_spinner("Loading transactions..."):
        try:
            result = state.app.transaction.list_transactions(
                queries=queries, limit=limit
            )
        except DatabaseError as e:
            logger.critical(e, exc_info=True)
            ctx.exit(1)
        except ValueError as e:
            logger.error(e, exc_info=True)
            ctx.exit(1)

    if result.total == 0:
        msg = "No transactions " + (
            "match your query." if queries else "found in the database."
        )
        output.display_warning(msg)
    else:
        output.display_dataframe(
            result.data,
            format,
            TransactionRead.rich_format_map(),
            extra_message=f"Showing {limit:,} of {result.total:,} transactions."
            if result.total > limit
            else None,
        )


@command("add")
@click.argument(
    "transaction_date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    metavar="<transaction_date>",
    required=False,
)
@click.argument(
    "transaction_type",
    type=TransactionType,
    metavar="<transaction_type>",
    required=False,
)
@click.argument("description", type=str, metavar="[<description>]", required=False)
@click.argument("amount", type=decimal.Decimal, metavar="[<amount>]", required=False)
@click.argument("units", type=decimal.Decimal, metavar="[<units>]", required=False)
@click.argument("account_id", type=int, metavar="[<account_id>]", required=False)
@click.argument("security_key", type=str, metavar="[<security_key>]", required=False)
@flags.common_options
@flags.no_input()
@click.pass_context
def add(
    ctx: click.Context,
    transaction_date: datetime.date,
    transaction_type: TransactionType,
    description: str,
    amount: decimal.Decimal,
    units: decimal.Decimal,
    account_id: int,
    security_key: str,
) -> None:
    """Create a new transaction.

    To create transactions interactively, run `niveshpy transactions add` without any arguments.

    To add a transaction non-interactively, provide all required arguments along with an optional --no-input flag.

    \b
    Arguments:
        <transaction_date> : Date of the transaction in YYYY-MM-DD format.
        <transaction_type> : Type of the transaction (either "purchase" or "sale").
        <description> : Description of the transaction.
        <amount> : Amount of money involved in the transaction.
        <units> : Number of units involved in the transaction.
        <account_id> : ID of the account associated with the transaction.
        <security_key> : Key of the security involved in the transaction.
    """  # noqa: D301
    state = ctx.ensure_object(AppState)
    if state.no_input:
        # Check that all required arguments are provided
        missing_args = [
            arg_name
            for arg_name, arg_value in {
                "transaction_date": transaction_date,
                "transaction_type": transaction_type,
                "description": description,
                "amount": amount,
                "units": units,
                "account_id": account_id,
                "security_key": security_key,
            }.items()
            if arg_value is None
        ]
        if missing_args:
            output.display_error(
                f"Missing required arguments for non-interactive mode: {missing_args}"
            )
            ctx.exit(1)

        # If all required arguments are provided, add the transaction
        try:
            result = state.app.transaction.add_transaction(
                transaction_date=transaction_date,
                transaction_type=transaction_type,
                description=description,
                amount=amount,
                units=units,
                account_id=account_id,
                security_key=security_key,
                source="cli",
            )
            output.display_success(
                f"Transaction added successfully with ID: {result.data}"
            )
        except DatabaseError as e:
            logger.critical(e, exc_info=True)
            ctx.exit(1)
        except ValueError as e:
            logger.error(e, exc_info=True)
            ctx.exit(1)

    else:
        output.display_message("Adding a new transaction.")
        output.display_message(
            textwrap.dedent("""
                Any command-line arguments will be used as defaults.
                Use arrow keys to navigate, and [i]Enter[/i] to accept defaults.
                Use [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.
            """)
        )
        while True:
            transaction_date = datetime.datetime.strptime(
                inquirer.text(
                    message="Transaction Date (YYYY-MM-DD):",
                    validate=inputs.validate_date,
                    default=transaction_date.strftime("%Y-%m-%d")
                    if transaction_date
                    else "",
                ).execute(),
                "%Y-%m-%d",
            ).date()

            transaction_type = inquirer.select(
                message="Transaction Type:",
                choices=list(TransactionType),
                default=transaction_type,
            ).execute()

            description = inquirer.text(
                message="Description:",
                validate=validator.EmptyInputValidator(),
                default=description if description else "",
            ).execute()

            amount = decimal.Decimal(
                inquirer.number(
                    message="Amount:",
                    float_allowed=True,
                    validate=validator.EmptyInputValidator(),
                    replace_mode=True,
                    default=amount,
                ).execute()
            )

            units = decimal.Decimal(
                inquirer.number(
                    message="Units:",
                    float_allowed=True,
                    validate=validator.EmptyInputValidator(),
                    replace_mode=True,
                    default=units,
                ).execute()
            )

            # Fetch accounts for selection
            accounts = state.app.transaction.get_account_choices()
            if not accounts:
                output.display_error(
                    "No accounts found in the database. Please add an account first."
                )
                ctx.exit(1)

            account_id = inquirer.fuzzy(
                message="Select Account:",
                choices=accounts,
                validate=validator.NumberValidator(
                    message="Please select a valid account."
                ),
                default=account_id,
            ).execute()

            # Fetch securities for selection
            securities = state.app.transaction.get_security_choices()
            if not securities:
                output.display_error(
                    "No securities found in the database. Please add a security first."
                )
                ctx.exit(1)

            security_key = inquirer.fuzzy(
                message="Select Security:",
                choices=securities,
                validate=validator.EmptyInputValidator(),
                default=security_key,
            ).execute()

            try:
                result = state.app.transaction.add_transaction(
                    transaction_date=transaction_date,
                    transaction_type=transaction_type,
                    description=description,
                    amount=amount,
                    units=units,
                    account_id=int(account_id),
                    security_key=security_key,
                    source="cli",
                )
                output.display_success(
                    f"Transaction added successfully with ID: {result.data}"
                )
            except DatabaseError as e:
                logger.critical(e, exc_info=True)
                ctx.exit(1)
            except ValueError as e:
                logger.error(e, exc_info=True)
                ctx.exit(1)

            output.display_message("Adding another transaction...")
            output.display_message("(Press Ctrl+C or Ctrl+D to exit.)")


@command("delete")
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
    """Delete a transaction based on a query.

    If no key is provided, you will be prompted to select from existing transactions.
    The query will be used to search for transactions by ID first.
    If no exact match is found, a text search will be performed based on various attributes.
    If multiple transactions match the provided query, you will be prompted to select one.

    Associated accounts and securities will not be deleted.

    When running in a non-interactive mode, --force must be provided to confirm deletion. Additionally, the <query> must match exactly one transaction ID.
    """
    state = ctx.ensure_object(AppState)

    if state.no_input and not force:
        output.display_error(
            "When running in non-interactive mode, --force must be provided to confirm deletion."
        )
        ctx.exit(1)

    inquirer_style = get_style({}, style_override=state.no_color)

    resolution = state.app.transaction.resolve_transaction(
        queries, limit, allow_ambiguous=not state.no_input
    )

    if resolution.status == ResolutionStatus.NOT_FOUND:
        output.display_error(
            "No transactions found matching the provided query. If running in non-interactive mode, ensure the query matches a transaction ID exactly."
        )
        ctx.exit(1)
    elif resolution.status == ResolutionStatus.EXACT:
        transaction = resolution.exact
        if transaction is None:
            logger.error(
                "Transaction resolution failed unexpectedly. Please report this bug."
            )
            logger.debug("Resolution object: %s", resolution)
            ctx.exit(1)

        if dry_run or not force:
            output.display_message(
                "The following transaction will be deleted:", transaction
            )
            if (
                not dry_run
                and not inquirer.confirm(
                    "Are you sure you want to delete this transaction?",
                    default=False,
                    style=inquirer_style,
                ).execute()
            ):
                logger.info("Transaction deletion aborted by user.")
                ctx.abort()

    elif resolution.status == ResolutionStatus.AMBIGUOUS:
        if state.no_input or not resolution.candidates:
            output.display_error(
                "The provided query is ambiguous and may match multiple securities. Please refine your query."
            )
            ctx.exit(1)

        choices = [
            control.Choice(
                txn.id,
                name=f"{txn.id}: [{txn.transaction_date}] {txn.type} of {txn.security} (Account: {txn.account}) - {txn.description} for {txn.amount} ({txn.units} units)",
            )
            for txn in resolution.candidates
        ]
        transaction_id = inquirer.fuzzy(
            message="Multiple transactions found. Select one to delete:",
            choices=choices,
            validate=validator.NumberValidator(),
            style=inquirer_style,
        ).execute()

        transaction = state.app.transaction.resolve_transaction(
            (str(transaction_id),), 1, False
        ).exact
        if transaction is None:
            logger.error(
                "Selected transaction could not be found. It may have been deleted already."
            )
            logger.debug("Resolution object: %s", resolution)
            ctx.exit(1)

        if not force:
            output.display_message(
                "You have selected the following transaction:", transaction
            )
            if (
                not dry_run
                and not inquirer.confirm(
                    "Are you sure you want to delete this transaction?",
                    default=False,
                    style=inquirer_style,
                ).execute()
            ):
                logger.info("Transaction deletion aborted by user.")
                ctx.abort()

    if dry_run:
        output.display_message("Dry Run: No changes were made.")
        ctx.exit()

    with output.loading_spinner(f"Deleting transaction '{transaction.id}'..."):
        deleted = state.app.transaction.delete_transaction(transaction.id)
        if deleted:
            output.display_success(
                f"Transaction with ID {transaction.id} was deleted successfully.",
            )
        else:
            logger.error(
                "Failed to delete transaction %s. It may have already been deleted.",
                transaction.id,
            )
            logger.debug("Resolution object: %s", resolution)


transactions.add_command(show)
transactions.add_command(add)
transactions.add_command(delete)

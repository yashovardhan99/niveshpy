"""CLI API for transactions."""

import datetime
import decimal
import json
import textwrap
from pathlib import Path

import click

from niveshpy.cli.utils import essentials, flags, inputs
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
    format_account,
    format_date,
    format_datetime,
    format_decimal,
    format_security,
    format_transaction_type,
)
from niveshpy.cli.utils.models import Column, OutputFormat
from niveshpy.cli.utils.overrides import command
from niveshpy.core.app import AppState
from niveshpy.core.converter import get_csv_converter, get_json_converter
from niveshpy.core.logging import logger
from niveshpy.exceptions import InvalidInputError, ResourceNotFoundError
from niveshpy.models.transaction import TransactionType


@essentials.group()
def cli() -> None:
    """Wrapper group for transaction-related commands."""


@command("list")
@click.argument("queries", default=(), required=False, metavar="[<queries>]", nargs=-1)
@flags.limit("accounts", default=30)
@flags.offset("accounts", default=0)
@flags.output("format")
@flags.output_file()
@click.option(
    "--cost",
    is_flag=True,
    default=False,
    help="Show cost basis information. Calculating cost basis may take longer.",
)
@click.pass_context
def show(
    ctx: click.Context,
    queries: tuple[str, ...],
    limit: int,
    offset: int,
    format: OutputFormat,
    output_file: Path | None,
    cost: bool,
) -> None:
    """List all transactions.

    Optionally provide a text QUERY to filter transactions by various attributes.

    View the documentation at https://yashovardhan99.github.io/niveshpy/cli/transactions/ for examples.
    """
    state = ctx.ensure_object(AppState)
    with loading_spinner("Loading transactions..."):
        result = state.app.transaction.list_transactions(
            queries=queries, limit=limit, offset=offset, cost=cost
        )

    if len(result) == 0:
        msg = "No transactions " + (
            "match your query." if queries else "found in the database."
        )
        display_warning(msg)
        ctx.exit()

    extra_message = (
        f"Showing first {limit:,} transactions."
        if len(result) == limit and offset == 0
        else (
            f"Showing transactions {offset + 1:,} to {offset + len(result):,}."
            if offset > 0
            else None
        )
    )
    with capture_for_pager(enabled=output_file is None or format == OutputFormat.TABLE):
        if format == OutputFormat.TABLE:
            if output_file:
                display_warning(
                    "Output file specified, but table format does not support file output. Ignoring --output-file flag."
                )
            if extra_message:
                display(extra_message)

            columns = [
                Column("id", style="dim", justify="right"),
                Column(
                    "transaction_date",
                    name="Date",
                    formatter=format_date,
                    style="cyan",
                ),
                Column("type", formatter=format_transaction_type),
                Column("description"),
                Column("security", formatter=format_security),
                Column("amount", formatter=format_decimal, style="bold"),
                Column("units", formatter=format_decimal, style="cyan"),
                Column("account", formatter=format_account, style="dim"),
                Column("created", style="dim", formatter=format_datetime),
                Column("source", style="dim"),
            ]
            if cost:
                columns.insert(
                    6,
                    Column(
                        "cost",
                        formatter=lambda cost: (
                            format_decimal(cost) if cost is not None else ""
                        ),
                        style="bold magenta",
                    ),
                )
            table = build_table(result, columns)
            display(table)
        elif format == OutputFormat.CSV:
            c = get_csv_converter()
            fields = [
                "id",
                "transaction_date",
                "type",
                "description",
                "security",
                "amount",
                "units",
                "account",
                "created",
                "source",
            ]
            if cost:
                fields.insert(6, "cost")
            csv = build_csv(
                c.unstructure(result), fields=fields, output_file=output_file
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


@command("add")
@click.argument(
    "transaction_date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    metavar="[<transaction_date>]",
    required=False,
)
@click.argument(
    "transaction_type",
    type=TransactionType,
    metavar="[<transaction_type>]",
    required=False,
)
@click.argument("description", type=str, metavar="[<description>]", required=False)
@click.argument("amount", type=decimal.Decimal, metavar="[<amount>]", required=False)
@click.argument("units", type=decimal.Decimal, metavar="[<units>]", required=False)
@click.argument("account_id", type=int, metavar="[<account_id>]", required=False)
@click.argument("security_key", type=str, metavar="[<security_key>]", required=False)
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
        transaction_date : Date of the transaction in YYYY-MM-DD format.
        transaction_type : Type of the transaction (either "purchase" or "sale").
        description : Description of the transaction.
        amount : Amount of money involved in the transaction.
        units : Number of units involved in the transaction.
        account_id : ID of the account associated with the transaction.
        security_key : Key of the security involved in the transaction.
    """  # noqa: D301
    from InquirerPy import inquirer, validator

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
            display_error(
                f"Missing required arguments for non-interactive mode: {missing_args}"
            )
            ctx.exit(1)

        # If all required arguments are provided, add the transaction
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
        display_success(f"Transaction added successfully with ID: {result}")
    else:
        display("Adding a new transaction.")
        display(
            textwrap.dedent(
                """
                Any command-line arguments will be used as defaults.
                Use arrow keys to navigate, and [i]Enter[/i] to accept defaults.
                Use [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.
            """
            )
        )
        while True:
            transaction_date = datetime.datetime.strptime(
                inquirer.text(
                    message="Transaction Date (YYYY-MM-DD):",
                    validate=inputs.validate_date,
                    default=(
                        transaction_date.strftime("%Y-%m-%d")
                        if transaction_date
                        else ""
                    ),
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
                display_error(
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
                display_error(
                    "No securities found in the database. Please add a security first."
                )
                ctx.exit(1)

            security_key = inquirer.fuzzy(
                message="Select Security:",
                choices=securities,
                validate=validator.EmptyInputValidator(),
                default=security_key,
            ).execute()

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
            display_success(f"Transaction added successfully with ID: {result}")

            display("Adding another transaction...")
            display("(Press Ctrl+C or Ctrl+D to exit.)")


@command("delete")
@click.argument("queries", required=False, metavar="[<queries>]", default=(), nargs=-1)
@flags.limit("limit", default=100)
@flags.no_input()
@flags.force()
@flags.dry_run()
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
    from InquirerPy import get_style, inquirer, validator
    from InquirerPy.base.control import Choice

    state = ctx.ensure_object(AppState)

    if state.no_input and not force:
        raise InvalidInputError(
            state,
            "When running in non-interactive mode, --force must be provided to confirm deletion.",
        )

    inquirer_style = get_style({}, style_override=state.no_color)

    candidates = state.app.transaction.resolve_transaction(
        queries, limit, allow_ambiguous=not state.no_input
    )

    if not candidates:
        raise ResourceNotFoundError("transaction", " ".join(queries))
    elif len(candidates) == 1:
        transaction = candidates[0]
    else:
        choices: list[Choice] = [
            Choice(
                txn.id,
                name=(
                    f"{txn.id}: [{txn.transaction_date}] {txn.type} of "
                    f"'{txn.security.name}' for {txn.amount} ({txn.units} units) "
                    f"(Account: '{txn.account.name}') "
                    f"- {txn.description}"
                ),
            )
            for txn in candidates
            if txn.security is not None and txn.account is not None
        ]
        transaction_id = inquirer.fuzzy(
            message="Multiple transactions found. Select one to delete:",
            choices=choices,
            validate=validator.NumberValidator(),
            style=inquirer_style,
        ).execute()

        transaction = state.app.transaction.resolve_transaction(
            (str(transaction_id),), limit=1, allow_ambiguous=False
        )[0]

    if dry_run or not force:
        display("You have selected the following transaction:")
        columns = [
            Column("id", style="dim", justify="right"),
            Column(
                "transaction_date",
                name="Date",
                formatter=format_date,
                style="cyan",
            ),
            Column("type", formatter=format_transaction_type),
            Column("description"),
            Column("security", formatter=format_security),
            Column("amount", formatter=format_decimal, style="bold"),
            Column("units", formatter=format_decimal, style="cyan"),
            Column("account", formatter=format_account, style="dim"),
        ]
        table = build_table((transaction,), columns)
        display(table)
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
        display("Dry Run: No changes were made.")
        ctx.exit()

    with loading_spinner(f"Deleting transaction '{transaction.id}'..."):
        deleted = state.app.transaction.delete_transaction(transaction.id)
        if deleted:
            display_success(
                f"Transaction with ID {transaction.id} was deleted successfully.",
            )
        else:
            msg = f"Transaction with ID {transaction.id} could not be deleted."
            raise InvalidInputError(state, msg)


cli.add_command(show)
cli.add_command(add)
cli.add_command(delete)

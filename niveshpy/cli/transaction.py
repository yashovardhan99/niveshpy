"""CLI API for transactions."""

import datetime
import decimal
import textwrap
import click
from niveshpy.cli.utils import flags, inputs
from niveshpy.cli.utils.overrides import command, group
from niveshpy.cli.app import AppState
from niveshpy.db.database import DatabaseError
from niveshpy.models.transaction import (
    TransactionRead,
    TransactionType,
)
from niveshpy.cli.utils.style import (
    OutputFormat,
    console,
    error_console,
    format_dataframe,
    rich_click_pager,
)
from niveshpy.core.logging import logger
from InquirerPy import inquirer, validator


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
    format: OutputFormat,
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
    with error_console.status("Loading transactions..."):
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
            error_console.print(msg, style="yellow")
            ctx.exit()

        out = format_dataframe(result.data, format, TransactionRead.rich_format_map())

    with rich_click_pager(console):
        if result.total > limit and console.is_terminal:
            console.print(
                f"Showing {limit:,} of {result.total:,} transactions.", style="yellow"
            )
        console.print_json(out) if format == OutputFormat.JSON and isinstance(
            out, str
        ) else console.print(out)


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
@click.argument("description", type=str, metavar="<description>", required=False)
@click.argument("amount", type=decimal.Decimal, metavar="<amount>", required=False)
@click.argument("units", type=decimal.Decimal, metavar="<units>", required=False)
@click.argument("account_id", type=int, metavar="<account_id>", required=False)
@click.argument("security_key", type=str, metavar="<security_key>", required=False)
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
            error_console.print(
                f"Missing required arguments for non-interactive mode: {', '.join(missing_args)}",
                style="red",
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
            console.print(
                f"Transaction added successfully with ID: {result.data}",
                style="green",
            )
        except DatabaseError as e:
            logger.critical(e, exc_info=True)
            ctx.exit(1)
        except ValueError as e:
            logger.error(e, exc_info=True)
            ctx.exit(1)

    else:
        console.print("Adding a new transaction.")
        console.print(
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
                error_console.print(
                    "No accounts found in the database. Please add an account first.",
                    style="red",
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
                error_console.print(
                    "No securities found in the database. Please add a security first.",
                    style="red",
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
                console.print(
                    f"Transaction added successfully with ID: {result.data}",
                    style="green",
                )
            except DatabaseError as e:
                logger.critical(e, exc_info=True)
                ctx.exit(1)
            except ValueError as e:
                logger.error(e, exc_info=True)
                ctx.exit(1)

            console.print("Adding another transaction...")
            console.print("(Press Ctrl+C or Ctrl+D to exit.)")


transactions.add_command(show)
transactions.add_command(add)

"""CLI API for transactions."""

from datetime import datetime, date
from decimal import Decimal
from textwrap import dedent

import click
import polars as pl
from niveshpy.core.validators import validate_date
from niveshpy.models.transaction import Transaction, TransactionType
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import NumberValidator, EmptyInputValidator


from niveshpy.services.app import Application


@click.group(invoke_without_command=True)
@click.pass_context
def transactions(ctx: click.Context) -> None:
    """List, add, or delete transactions."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(show)


@transactions.command("list")
@click.pass_obj
def show(app: Application) -> None:
    """List all transactions."""
    click.echo(app.transaction_service.get_transactions())


@transactions.command()
@click.pass_obj
def add(
    app: Application,
) -> None:
    """Add new transactions."""
    click.echo(
        dedent("""
               Adding new transaction.
               Any command-line arguments will be used as defaults.
               Please ensure that the account and security exist in the database.
               Use Ctrl+Z to skip optional fields.
               Use Ctrl+C to cancel.
               """)
    )
    txn_date = inquirer.text(
        message="Transaction Date (YYYY-MM-DD)",
        default=date.today().strftime("%Y-%m-%d"),
        validate=validate_date,
        invalid_message="Please enter a valid date in YYYY-MM-DD format.",
    ).execute()

    txn_date = datetime.strptime(txn_date, "%Y-%m-%d").date()

    txn_type = inquirer.select(
        message="Transaction Type",
        choices=[Choice(t, name=t.name) for t in TransactionType],
    ).execute()

    description: str = inquirer.text(message="Description").execute()
    units = Decimal(
        inquirer.text(
            message="Units", validate=NumberValidator(float_allowed=True)
        ).execute()
    )
    amount = Decimal(
        inquirer.text(
            message="Amount", validate=NumberValidator(float_allowed=True)
        ).execute()
    )

    securities = app.security_service.get_securities()
    if securities.is_empty():
        click.secho("No securities found. Please add a security first.", fg="red")
        return

    security_choices = [
        Choice(security["key"], name=security["display_name"])
        for security in securities.select(
            "key",
            pl.concat_str(
                pl.col("name"), pl.lit(" ("), pl.col("key"), pl.lit(")")
            ).alias("display_name"),
        ).to_dicts()
    ]

    security_key: str = inquirer.fuzzy(
        message="Select Security:",
        choices=security_choices,
        instruction="(Type to filter, use arrow keys to navigate, Enter to select)",
        validate=EmptyInputValidator(),
    ).execute()

    accounts = app.account_service.get_accounts()
    if accounts.is_empty():
        click.secho("No accounts found. Please add an account first.", fg="red")
        return

    account_choices = [
        Choice(str(account["id"]), name=f"{account['institution']} - {account['name']}")
        for account in accounts.to_dicts()
    ]

    account_key: str = inquirer.fuzzy(
        message="Select Account:",
        choices=account_choices,
        instruction="(Type to filter, use arrow keys to navigate, Enter to select)",
        validate=EmptyInputValidator(),
    ).execute()

    transaction = Transaction(
        transaction_date=txn_date,
        type=TransactionType(txn_type),
        description=description,
        amount=amount,
        units=units,
        security_key=security_key,
        account_key=account_key,
    )
    click.echo(transaction)
    app.transaction_service.add_transactions(pl.DataFrame([transaction.__dict__]))
    click.secho("Transaction added successfully.", fg="green")

"""CLI commands for managing securities."""

from textwrap import dedent
import click
from rich.console import Console

from niveshpy.core.style import get_polars_print_config, rich_click_pager
from niveshpy.db.query import QueryOptions
from niveshpy.models.security import Security, SecurityCategory, SecurityType
from niveshpy.services.app import Application
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import EmptyInputValidator


@click.group(invoke_without_command=True)
@click.pass_context
def securities(ctx: click.Context) -> None:
    """Manage securities."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(show)


@securities.command("list")
@click.argument("query", default="", required=False)
@click.option(
    "--limit",
    "-l",
    default=30,
    help="Number of securities to display.",
    show_default=True,
)
@click.pass_obj
def show(app: Application, query: str = "", limit: int = 30) -> None:
    """Show all securities."""
    console = Console()
    error_console = Console(stderr=True)
    with error_console.status("Loading securities..."):
        n = app.security_service.count_securities(
            QueryOptions(text_query=query if query else None)
        )
        if n == 0:
            msg = (
                "[bold yellow]No securities match your query."
                if query
                else "[bold yellow]No securities found in the database."
            )
            error_console.print(msg)
            return
        securities = app.security_service.get_securities(
            QueryOptions(text_query=query if query else None, limit=limit)
        ).pl()
        with get_polars_print_config():
            if console.is_terminal:
                out = securities.__str__()
            else:
                out = securities.write_csv(separator="\t")

    if console.is_terminal:
        with rich_click_pager(console):
            if n > limit:
                console.print(f"[bold yellow]Showing {limit:,} of {n:,} securities.")
            console.print(out)
    else:
        console.print(out)


@securities.command()
@click.argument("default_key", metavar="[KEY]", default="")
@click.argument("default_name", metavar="[NAME]", default="")
@click.argument(
    "default_category",
    required=False,
    type=click.Choice(SecurityCategory, case_sensitive=False),
    metavar="[CATEGORY]",
)
@click.argument(
    "default_type",
    required=False,
    type=click.Choice(SecurityType, case_sensitive=False),
    metavar="[TYPE]",
)
@click.pass_obj
def add(
    app: Application,
    default_key: str = "",
    default_name: str = "",
    default_category: str | None = None,
    default_type: str | None = None,
) -> None:
    """Add a new security."""
    console = Console(width=80)
    console.rule("[bold blue]Add New Security")
    console.print(
        dedent("""
            Any command-line arguments will be used as defaults.
            Use arrow keys to navigate, and [i]Enter[/i] to accept defaults.
            Use [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.
        """)
    )

    while True:
        security_key = inquirer.text(
            message="Security Key",
            instruction="(A unique identifier for the security, e.g., ticker symbol or ISIN)",
            long_instruction="If another security with the same key exists, it will be updated.",
            validate=EmptyInputValidator(),
            default=default_key,
        ).execute()
        name = inquirer.text(
            message="Security Name",
            instruction="(The full name of the security)",
            validate=EmptyInputValidator(),
            default=default_name,
        ).execute()
        category = inquirer.select(
            message="Security Category",
            choices=[Choice(cat, name=cat.name) for cat in SecurityCategory],
            default=default_category,
        ).execute()
        security_type = inquirer.select(
            message="Security Type",
            choices=[Choice(t, name=t.name) for t in SecurityType],
            default=default_type,
        ).execute()

        security = Security(
            key=security_key,
            name=name,
            category=category,
            type=security_type,
        )

        console.print("\nYou have entered the following details:")
        console.print(security)
        confirm = inquirer.confirm(
            message="Add this security to the database?",
            default=True,
        ).execute()
        if not confirm:
            console.print("[bold red]Aborted![/bold red] Security not added.")
            break
        action = app.security_service.add_single_security(security)
        action = "inserted" if action == "INSERT" else "updated"
        console.print(f"[bold green]Security '{name}' was {action} successfully.")

        if default_key:
            # If defaults were provided via command-line arguments, exit after one iteration
            break

        console.print()

        console.rule("[bold blue]Add Next Security")
        console.print("Press [i]Ctrl+C[/i] or [i]Ctrl+D[/i] to quit.")


@securities.command()
@click.argument("key", required=False)
@click.option("--all", "-a", is_flag=True, help="List all securities before deletion.")
@click.pass_obj
def delete(app: Application, key: str | None = None, all: bool = False) -> None:
    """Delete a security by its key."""
    console = Console(width=80)
    if not key:
        # If no key provided, get user to select from existing securities

        with console.status("Loading securities..."):
            # Load securities from the database
            n = app.security_service.count_securities()
            if n == 0:
                console.print("[bold yellow]No securities found in the database.")
                return
            if not all and n > 10_000:
                console.print(
                    f"[bold yellow]:warning: There are {n:,} securities in the database. "
                    "Only 10,000 will be loaded for selection due to performance constraints. "
                    "You can use --all to load all securities, but it may be very slow."
                )

            securities_df = app.security_service.get_securities(
                QueryOptions(limit=10_000) if not all else QueryOptions()
            ).pl()
            choices = [
                Choice(row["key"], name=f"{row['key']} - {row['name']}")
                for row in securities_df.to_dicts()
            ]

        # Prompt user to select a security
        key = inquirer.fuzzy(
            message="Select a security to delete",
            choices=choices,
            validate=EmptyInputValidator(),
        ).execute()

    if not key:
        # If still no key, abort
        console.print("[bold red]Aborted![/bold red] No security key provided.")
        return

    if not inquirer.confirm(
        f"Are you sure you want to delete the security with key '{key}'?",
        default=False,
    ).execute():
        console.print("[bold red]Aborted![/bold red] Security not deleted.")
        return
    with console.status(f"Deleting security '{key}'..."):
        deleted = app.security_service.delete_security(key)
        if deleted:
            console.print(f"[bold green]Security '{key}' was deleted successfully.")
        else:
            console.print(
                f"[bold yellow]No security found with key '{key}'.[/bold yellow]"
            )

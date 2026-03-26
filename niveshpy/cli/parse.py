"""CLI API for parsing files."""

import textwrap
from pathlib import Path

import click
import click.shell_completion
from InquirerPy import get_style, inquirer
from rich import progress

from niveshpy.cli.utils import flags, overrides
from niveshpy.cli.utils import output as output
from niveshpy.core import parsers as parser_registry
from niveshpy.core.app import AppState
from niveshpy.core.logging import logger
from niveshpy.exceptions import ResourceNotFoundError


class ParserType(click.ParamType):
    """Custom Click parameter type for selecting a parser."""

    name = "parser"

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ):
        """Provide shell completion for parser names."""
        if parser_registry.is_empty():
            parser_registry.discover_installed_parsers()
        return [
            click.shell_completion.CompletionItem(
                key, help=factory.get_parser_info().name
            )
            for key, factory in parser_registry.list_parsers_starting_with(incomplete)
        ]


@overrides.command("parse")
@flags.no_input()
@click.pass_context
@click.argument("parser_key", type=ParserType(), metavar="<parser>")
@click.argument(
    "file_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path, readable=True),
    metavar="<file-path>",
)
@click.option(
    "--password-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path, readable=True),
    default=None,
    help="Path to a file containing the password for encrypted files.",
)
def parse(
    ctx: click.Context, parser_key: str, file_path: Path, password_file: Path
) -> None:
    """Parse custom statements and documents.

    Parse financial documents using the specified parser and file.

    Required Args:

    \b
    * parser_key (str): The parser to use. Example: 'cas'.
    * file_path (str): Path to the file to parse.
    """  # noqa: D301
    state = ctx.ensure_object(AppState)
    inquirer_style = get_style({}, style_override=state.no_color)

    with output.loading_spinner(f"Looking for parser {parser_key}..."):
        if parser_registry.is_empty():
            parser_registry.discover_installed_parsers(parser_key)
        parser_factory = parser_registry.get_parser(parser_key)

    if parser_factory is None:
        raise ResourceNotFoundError("parser", parser_key)

    parser_info = parser_factory.get_parser_info()

    password = None if password_file is None else password_file.read_text().strip()

    if parser_info.password_required and password is None:
        if state.no_input:
            logger.error("Password is required for this parser but not provided.")
            ctx.exit(1)
        else:
            logger.info(
                "Password is required for this parser but not provided. Asking interactively."
            )
            password = output.ask_password()

    with output.loading_spinner(f"Loading parser {parser_key}..."):
        parser = parser_factory.create_parser(
            file_path,
            password=password,
        )

    if not state.no_input:
        output.display_message(
            textwrap.dedent(f"""
                    The parser ({parser_info.name}) will now parse and store data from the file.
                    This may take some time depending on the file size and content.
                    [yellow]Existing data may be updated or overwritten.[/yellow]
            """)
        )
        if not inquirer.confirm(
            "Do you want to continue?", style=inquirer_style, default=True
        ).execute():
            output.display_error("Operation cancelled by user.")
            ctx.abort()

    prog = output.get_progress_bar()
    task_map: dict[str, progress.TaskID] = {}

    def update_progress(stage: str, current: int, total: int) -> None:
        """Update progress bar."""
        if stage not in task_map:
            task_map[stage] = prog.add_task(
                f"Processing {stage}...", total=total if total != -1 else None
            )
        if total != -1:
            prog.start_task(task_map[stage])
            prog.update(task_map[stage], total=total, completed=current)

    with prog:
        service = state.app.get_parsing_service(parser, update_progress)
        service.parse_and_store_all()

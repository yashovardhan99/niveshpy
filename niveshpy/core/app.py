"""Main application class to hold state for the CLI."""

from collections.abc import Callable
from dataclasses import dataclass
from niveshpy.db.database import Database
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.models.parser import Parser
from niveshpy.services.account import AccountService
from niveshpy.services.parsing import ParsingService
from niveshpy.services.security import SecurityService
from niveshpy.services.transaction import TransactionService


class Application:
    """Main application class to hold state for the CLI."""

    def __init__(self, db: Database):
        """Initialize the application with its services."""
        self._repos = RepositoryContainer(db)
        self._security: SecurityService | None = None
        self._account: AccountService | None = None
        self._transaction: TransactionService | None = None

    @property
    def security(self) -> SecurityService:
        """Return the security service."""
        if self._security is None:
            self._security = SecurityService(self._repos)
        return self._security

    @property
    def account(self) -> AccountService:
        """Return the account service."""
        if self._account is None:
            self._account = AccountService(self._repos)
        return self._account

    @property
    def transaction(self) -> TransactionService:
        """Return the transaction service."""
        if self._transaction is None:
            self._transaction = TransactionService(self._repos)
        return self._transaction

    def get_parsing_service(
        self,
        parser: Parser,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ParsingService:
        """Get the parsing service for the given parser key."""
        return ParsingService(parser, self._repos, progress_callback=progress_callback)


@dataclass
class AppState:
    """State for the application."""

    debug: bool = False
    no_input: bool = False
    no_color: bool = False

    @property
    def app(self) -> Application:
        """The main application instance."""
        return self._app

    @app.setter
    def app(self, value: Application) -> None:
        self._app = value

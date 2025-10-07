"""Main application class to hold state for the CLI."""

from dataclasses import dataclass
from niveshpy.db.database import Database
from niveshpy.services.account import AccountService
from niveshpy.services.security import SecurityService
from niveshpy.services.transaction import TransactionService


class Application:
    """Main application class to hold state for the CLI."""

    def __init__(self, db: Database):
        """Initialize the application with its services."""
        self._db = db
        self.security_service = SecurityService(db)
        self.account_service = AccountService(db)
        self.transaction_service = TransactionService(db)


@dataclass
class AppState:
    """State for the application."""

    debug: bool = False
    no_input: bool = False

    @property
    def app(self) -> Application:
        """The main application instance."""
        return self._app

    @app.setter
    def app(self, value: Application) -> None:
        self._app = value

"""Application-level services for Niveshpy."""

from niveshpy.db.database import Database
from niveshpy.services.account import AccountService
from niveshpy.services.security import SecurityService
from niveshpy.services.transaction import TransactionService


class Application:
    """Main application class to hold all services."""

    def __init__(self, db: Database):
        """Initialize the application with its services."""
        self._db = db
        self.security_service = SecurityService(db)
        self.account_service = AccountService(db)
        self.transaction_service = TransactionService(db)

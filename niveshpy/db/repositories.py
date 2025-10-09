"""Holds the database repositories for the application."""

from niveshpy.db.account import AccountRepository
from niveshpy.db.database import Database
from niveshpy.db.security import SecurityRepository
from niveshpy.db.transaction import TransactionRepository


class RepositoryContainer:
    """Holds the database repositories for the application."""

    def __init__(self, db: Database):
        """Initialize all repositories with the given database connection."""
        self._db = db
        self._security: SecurityRepository | None = None
        self._account: AccountRepository | None = None
        self._transaction: TransactionRepository | None = None

    @property
    def security(self) -> SecurityRepository:
        """Get the SecurityRepository instance."""
        if self._security is None:
            self._security = SecurityRepository(self._db)
        return self._security

    @property
    def account(self) -> AccountRepository:
        """Get the AccountRepository instance."""
        if self._account is None:
            self._account = AccountRepository(self._db)
        return self._account

    @property
    def transaction(self) -> TransactionRepository:
        """Get the TransactionRepository instance."""
        if self._transaction is None:
            self._transaction = TransactionRepository(self._db)
        return self._transaction

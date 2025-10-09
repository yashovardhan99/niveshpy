"""Transaction service for managing user transactions."""

from niveshpy.db.repositories import RepositoryContainer


class TransactionService:
    """Service handler for the transactions command group."""

    def __init__(self, repos: RepositoryContainer):
        """Initialize the TransactionService with repositories."""
        self._repos = repos

    def get_transactions(self):
        """Get all transactions."""
        return self._repos.transaction.get_transactions()

    def add_transactions(self, transactions):
        """Add new transactions."""
        return self._repos.transaction.add_transactions(transactions)

    def get_accounts(self):
        """Get all accounts."""
        return self._repos.account.get_accounts()

    def get_securities(self):
        """Get all securities."""
        return self._repos.security.get_securities()

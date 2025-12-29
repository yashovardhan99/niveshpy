"""Holds the database repositories for the application."""

from niveshpy.db.database import Database
from niveshpy.db.prices import PriceRepository


class RepositoryContainer:
    """Holds the database repositories for the application."""

    def __init__(self, db: Database):
        """Initialize all repositories with the given database connection."""
        self._db = db
        self._price: PriceRepository | None = None

    @property
    def price(self) -> PriceRepository:
        """Get the PriceRepository instance."""
        if self._price is None:
            self._price = PriceRepository(self._db)
        return self._price

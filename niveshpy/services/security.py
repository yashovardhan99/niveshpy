"""Service for handling security-related tasks."""

from collections.abc import Iterable
from niveshpy.db import Database
from niveshpy.models.security import Security
import polars as pl


class SecurityService:
    """Service for managing securities."""

    _table_name = "securities"

    def __init__(self, db: Database):
        """Initialize the SecurityService with a database connection."""
        self._db_conn = db.cursor()

    def _create_table(self) -> None:
        """Create the securities table if it doesn't exist."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._table_name} (
            key VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            type VARCHAR NOT NULL,
            category VARCHAR NOT NULL
        );
        """
        self._db_conn.execute(query)
        self._db_conn.commit()

    def add_securities(self, securities: Iterable[Security]) -> None:
        """Add new securities to the database."""
        self._create_table()
        self._db_conn.register("new_securities", pl.from_dicts(securities))
        self._db_conn.execute(
            f"""MERGE INTO {self._table_name} target
            USING (SELECT * FROM new_securities) AS new
            ON target.key = new.key
            WHEN MATCHED THEN UPDATE
            WHEN NOT MATCHED THEN INSERT BY NAME;
            """
        )
        self._db_conn.commit()

    def get_securities(self) -> pl.DataFrame:
        """Retrieve all securities from the database."""
        self._create_table()
        return self._db_conn.execute(
            f"SELECT key, name, type, category FROM {self._table_name}"
        ).pl()

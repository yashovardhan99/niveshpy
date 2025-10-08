"""Account database operations."""

from dataclasses import asdict
from itertools import starmap
from collections.abc import Iterable
from niveshpy.db.database import Database
from niveshpy.models.account import AccountRead, AccountWrite
import polars as pl
from niveshpy.core.logging import logger


class AccountRepository:
    """Repository for managing investment accounts."""

    _table_name = "accounts"

    def __init__(self, db: Database):
        """Initialize the AccountRepository."""
        self._db = db
        logger.info("Initializing AccountRepository")
        self._create_table()

    def _create_table(self):
        """Create the accounts table if it doesn't exist."""
        query = f"""
        CREATE SEQUENCE IF NOT EXISTS account_id_seq;
        CREATE TABLE IF NOT EXISTS {self._table_name} (
            id INTEGER PRIMARY KEY DEFAULT nextval('account_id_seq'),
            name VARCHAR NOT NULL,
            institution VARCHAR NOT NULL
        );
        """
        with self._db.cursor() as cursor:
            cursor.execute(query)
            cursor.commit()

    def get_accounts(self) -> pl.DataFrame:
        """Retrieve all accounts from the database."""
        with self._db.cursor() as cursor:
            return cursor.execute(
                f"SELECT id, name, institution FROM {self._table_name}"
            ).pl()

    def add_accounts(self, accounts: Iterable[AccountWrite]) -> Iterable[AccountRead]:
        """Add new accounts to the database."""
        with self._db.cursor() as cursor:
            cursor.register("new_accounts", pl.from_dicts(map(asdict, accounts)))
            data = cursor.execute(
                f"""MERGE INTO {self._table_name} target
                USING (SELECT * FROM new_accounts) AS new
                ON target.name = new.name AND target.institution = new.institution
                WHEN NOT MATCHED THEN INSERT BY NAME;

                FROM {self._table_name}
                ORDER BY id;
                """
            )
            cursor.commit()
            return starmap(AccountRead, data.fetchall())

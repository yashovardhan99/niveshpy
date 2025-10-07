"""Service for managing investment accounts."""

from dataclasses import asdict
from itertools import starmap
from collections.abc import Iterable
from typing import Literal, overload
from niveshpy.db.database import Database
from niveshpy.models.account import AccountRead, AccountWrite
import polars as pl


class AccountService:
    """Service for managing investment accounts."""

    _table_name = "accounts"

    def __init__(self, db: Database):
        """Initialize the AccountService."""
        self._db_conn = db.cursor()

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
        self._db_conn.execute(query)
        self._db_conn.commit()

    @overload
    def get_accounts(self, lazy: Literal[True]) -> pl.LazyFrame: ...

    @overload
    def get_accounts(self, lazy: Literal[False] = ...) -> pl.DataFrame: ...

    def get_accounts(self, lazy: bool = False) -> pl.DataFrame | pl.LazyFrame:
        """Retrieve all accounts from the database."""
        self._create_table()
        return self._db_conn.execute(
            f"SELECT id, name, institution FROM {self._table_name}"
        ).pl(lazy=lazy)

    def add_accounts(self, accounts: Iterable[AccountWrite]) -> Iterable[AccountRead]:
        """Add new accounts to the database."""
        self._create_table()
        self._db_conn.register("new_accounts", pl.from_dicts(map(asdict, accounts)))
        data = self._db_conn.execute(
            f"""MERGE INTO {self._table_name} target
            USING (SELECT * FROM new_accounts) AS new
            ON target.name = new.name AND target.institution = new.institution
            WHEN NOT MATCHED THEN INSERT BY NAME;

            FROM {self._table_name}
            ORDER BY id;
            """
        )
        self._db_conn.commit()
        return starmap(AccountRead, data.fetchall())

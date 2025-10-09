"""Account database operations."""

from dataclasses import asdict
from itertools import starmap
from collections.abc import Iterable
from typing import Literal, overload
from niveshpy.db.database import Database
from niveshpy.db.query import DEFAULT_QUERY_OPTIONS, QueryOptions, ResultFormat
from niveshpy.models.account import AccountRead, AccountWrite
import polars as pl
from niveshpy.core.logging import logger


class AccountRepository:
    """Repository for managing investment accounts in the database."""

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

    def count_accounts(self, options: QueryOptions = DEFAULT_QUERY_OPTIONS) -> int:
        """Count the number of accounts matching the query options."""
        query = f"SELECT COUNT(*) FROM {self._table_name}"
        params = []
        if options.text_query:
            query += " WHERE name ILIKE $1 OR institution ILIKE $1"
            like_pattern = f"%{options.text_query}%"
            params.append(like_pattern)
        query += ";"

        with self._db.cursor() as cursor:
            res = cursor.execute(query, params)
            count = res.fetchone()
            return count[0] if count is not None else 0

    @overload
    def search_accounts(
        self, options: QueryOptions, format: Literal[ResultFormat.POLARS]
    ) -> pl.DataFrame: ...

    @overload
    def search_accounts(
        self, options: QueryOptions, format: Literal[ResultFormat.SINGLE]
    ) -> tuple | None: ...

    @overload
    def search_accounts(
        self, options: QueryOptions, format: Literal[ResultFormat.LIST]
    ) -> list[tuple]: ...

    def search_accounts(
        self,
        options: QueryOptions = DEFAULT_QUERY_OPTIONS,
        format: ResultFormat = ResultFormat.POLARS,
    ) -> pl.DataFrame | tuple | None | list[tuple]:
        """Search for accounts matching the query options."""
        query = f"SELECT * FROM {self._table_name}"
        params = []
        if options.text_query:
            query += " WHERE name ILIKE $1 OR institution ILIKE $1"
            like_pattern = f"%{options.text_query}%"
            params.append(like_pattern)
        query += " ORDER BY id"
        if options.limit:
            query += " LIMIT ?"
            params.append(str(options.limit))
        if options.offset:
            query += " OFFSET ?"
            params.append(str(options.offset))
        query += ";"

        with self._db.cursor() as cursor:
            res = cursor.execute(query, params)
            if format == ResultFormat.POLARS:
                return res.pl()
            elif format == ResultFormat.SINGLE:
                return res.fetchone()
            else:
                return res.fetchall()

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

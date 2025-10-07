"""Service for handling security-related tasks."""

from collections.abc import Iterable
from dataclasses import asdict
from niveshpy.db.database import Database
from niveshpy.db.query import DEFAULT_QUERY_OPTIONS, QueryOptions
from niveshpy.db.result import Result
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

    def add_single_security(self, security: Security) -> str:
        """Add a single security to the database.

        If a security with the same key exists, it will be updated.
        Returns 'INSERT' if a new security was added, 'UPDATE' if an existing security
        was updated.
        """
        self._create_table()
        res = self._db_conn.execute(
            f"""INSERT OR REPLACE INTO {self._table_name} 
            (key, name, type, category)
            VALUES (?, ?, ?, ?)
            RETURNING merge_action;
            """,
            (security.key, security.name, security.type, security.category),
        ).fetchone()
        if res is None:
            raise RuntimeError("Failed to add or update the security.")
        self._db_conn.commit()
        return res[0]

    def add_securities(self, securities: Iterable[Security]) -> None:
        """Add new securities to the database."""
        securities_dicts = map(asdict, securities)
        self._create_table()
        self._db_conn.register("new_securities", pl.from_dicts(securities_dicts))
        self._db_conn.execute(
            f"""MERGE INTO {self._table_name} target
            USING (SELECT * FROM new_securities) AS new
            ON target.key = new.key
            WHEN MATCHED THEN UPDATE
            WHEN NOT MATCHED THEN INSERT BY NAME;
            """
        )
        self._db_conn.commit()

    def count_securities(self, options: QueryOptions = DEFAULT_QUERY_OPTIONS) -> int:
        """Count the number of securities in the database."""
        self._create_table()
        query = f"SELECT COUNT(*) FROM {self._table_name}"
        params = []
        if options.text_query:
            query += " WHERE key LIKE $1 OR name LIKE $1"
            like_pattern = f"%{options.text_query}%"
            params.append(like_pattern)
        res = self._db_conn.execute(query, tuple(params)).fetchone()
        return res[0] if res else 0

    def get_securities(self, options: QueryOptions = DEFAULT_QUERY_OPTIONS) -> Result:
        """Retrieve all securities from the database."""
        self._create_table()
        query = f"SELECT * FROM {self._table_name}"
        params = []
        if options.text_query:
            query += " WHERE key LIKE $1 OR name LIKE $1"
            like_pattern = f"%{options.text_query}%"
            params.append(like_pattern)

        query += " ORDER BY key"

        if options.limit is not None:
            query += " LIMIT ?"
            params.append(str(options.limit))
        if options.offset is not None:
            query += " OFFSET ?"
            params.append(str(options.offset))
        query += ";"
        res = self._db_conn.execute(query, tuple(params))
        return Result(res)

    def delete_security(self, key: str) -> bool:
        """Delete a security by its key.

        Returns True if a security was deleted, False otherwise.
        """
        self._create_table()
        res = self._db_conn.execute(
            f"DELETE FROM {self._table_name} WHERE key = ? RETURNING *;",
            (key,),
        )
        self._db_conn.commit()
        return res.fetchone() is not None

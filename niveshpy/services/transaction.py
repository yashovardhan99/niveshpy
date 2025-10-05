"""Transaction service for managing user transactions."""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from niveshpy.db import Database
    import polars as pl
    import pandas as pd


class TransactionService:
    """Service for managing transactions."""

    _table_name = "transactions"

    def __init__(self, db: "Database"):
        """Initialize the TransactionService with a database connection."""
        self._db_conn = db.cursor()

    def get_transactions(self) -> "pl.DataFrame":
        """Retrieve all transactions from the database."""
        self._create_table()
        return self._db_conn.sql(f"SELECT * FROM {self._table_name}").pl()

    def add_transactions(self, transactions: "pl.DataFrame | pd.DataFrame") -> None:
        """Add new transactions from a Polars DataFrame to the database."""
        self._create_table()
        self._db_conn.register("new_transactions", transactions)
        self._db_conn.execute(
            f"""MERGE INTO {self._table_name} target
            USING (SELECT * FROM new_transactions) AS new
            ON target.transaction_date = new.transaction_date
               AND target.type = new.type
               AND target.description = new.description
               AND target.amount = new.amount
               AND target.security_key = new.security_key
               AND target.account_key = new.account_key
            WHEN MATCHED THEN UPDATE
            WHEN NOT MATCHED THEN INSERT BY NAME;
            """
        )
        self._db_conn.commit()

    def delete_transactions(self, transactions: "pl.DataFrame | pd.DataFrame") -> None:
        """Delete transactions from the database."""
        self._create_table()
        self._db_conn.register("del_transactions", transactions)
        self._db_conn.execute(
            f"""
            MERGE INTO {self._table_name} target
            USING (SELECT * FROM del_transactions) AS del
            ON target.transaction_date = del.transaction_date
               AND target.type = del.type
               AND target.description = del.description
               AND target.amount = del.amount
               AND target.security_key = del.security_key
               AND target.account_key = del.account_key
            WHEN MATCHED THEN DELETE;
            """
        )
        self._db_conn.commit()

    def _create_table(self) -> None:
        """Create the transactions table if it doesn't exist."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._table_name} (
            transaction_date DATE,
            type TEXT,
            description TEXT,
            amount DECIMAL(24, 2),
            units DECIMAL(24, 3),
            security_key TEXT,
            account_key TEXT
        );
        """
        self._db_conn.execute(query)
        self._db_conn.commit()

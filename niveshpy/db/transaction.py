"""Transaction service for managing user transactions."""

import polars as pl
from niveshpy.db.database import Database
from niveshpy.core.logging import logger


class TransactionRepository:
    """Repository for managing transactions."""

    _table_name = "transactions"

    def __init__(self, db: "Database"):
        """Initialize the TransactionRepository with a database connection."""
        self._db = db
        logger.info("Initializing TransactionRepository.")
        self._create_table()

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
        with self._db.cursor() as cursor:
            cursor.execute(query)
            cursor.commit()

    def get_transactions(self) -> pl.DataFrame:
        """Retrieve all transactions from the database."""
        with self._db.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {self._table_name}")
            return cursor.pl()

    def add_transactions(self, transactions: pl.DataFrame) -> None:
        """Add new transactions from a Polars DataFrame to the database."""
        with self._db.cursor() as cursor:
            cursor.register("new_transactions", transactions)
            cursor.execute(
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
            cursor.commit()

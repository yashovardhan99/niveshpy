"""Transaction service for managing user transactions."""

from typing import Literal
from niveshpy.core.query import ast
from niveshpy.db.database import Database
from niveshpy.db.query import (
    DEFAULT_QUERY_OPTIONS,
    QueryOptions,
    ResultFormat,
    prepare_query_filters,
)
from niveshpy.core.logging import logger
import polars as pl


class TransactionRepository:
    """Repository for managing transactions."""

    _table_name = "transactions"

    _column_mappings = {
        ast.Field.ACCOUNT: ["accounts.name", "accounts.institution"],
        ast.Field.AMOUNT: ["amount"],
        ast.Field.DATE: ["transaction_date"],
        ast.Field.DESCRIPTION: ["description"],
        ast.Field.SECURITY: [
            "securities.key",
            "securities.name",
            "securities.type",
            "securities.category",
        ],
        ast.Field.TYPE: ["type"],
    }

    def __init__(self, db: "Database"):
        """Initialize the TransactionRepository with a database connection."""
        self._db = db

    def count_transactions(self, options: QueryOptions = DEFAULT_QUERY_OPTIONS) -> int:
        """Count the number of transactions matching the query options."""
        query = f"""
        SELECT COUNT(*) FROM {self._table_name} t
        INNER JOIN securities ON t.security_key = securities.key 
        INNER JOIN accounts ON t.account_id = accounts.id
        """
        if options.filters:
            filter_query, params = prepare_query_filters(
                options.filters, self._column_mappings
            )
            query += " WHERE " + filter_query
        else:
            params = ()
        query += ";"

        logger.debug("Executing count query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            res = cursor.execute(query, params)
            count = res.fetchone()
            return count[0] if count is not None else 0

    def search_transactions(
        self,
        options: QueryOptions = DEFAULT_QUERY_OPTIONS,
        format: Literal[ResultFormat.POLARS] = ResultFormat.POLARS,
    ) -> pl.DataFrame:
        """Search for transactions matching the query options."""
        query = f"""
        SELECT t.*, securities.name AS security_name, accounts.name AS account_name, accounts.institution AS account_institution
        FROM {self._table_name} t
        INNER JOIN securities ON t.security_key = securities.key 
        INNER JOIN accounts ON t.account_id = accounts.id
        """

        if options.filters:
            filter_query, _params = prepare_query_filters(
                options.filters, self._column_mappings
            )
            query += " WHERE " + filter_query
            params = list(_params)
        else:
            params = []

        query += " ORDER BY t.transaction_date DESC"
        if options.limit:
            query += " LIMIT ?"
            params.append(options.limit)
        query += ";"
        logger.debug("Executing search query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.pl()

    # def get_transactions(self) -> pl.DataFrame:
    #     """Retrieve all transactions from the database."""
    #     with self._db.cursor() as cursor:
    #         cursor.execute(f"SELECT * FROM {self._table_name}")
    #         return cursor.pl()

    # def add_transactions(self, transactions: pl.DataFrame) -> None:
    #     """Add new transactions from a Polars DataFrame to the database."""
    #     with self._db.cursor() as cursor:
    #         cursor.register("new_transactions", transactions)
    #         cursor.execute(
    #             f"""MERGE INTO {self._table_name} target
    #             USING (SELECT * FROM new_transactions) AS new
    #             ON target.transaction_date = new.transaction_date
    #            AND target.type = new.type
    #            AND target.description = new.description
    #            AND target.amount = new.amount
    #            AND target.security_key = new.security_key
    #            AND target.account_key = new.account_key
    #         WHEN MATCHED THEN UPDATE
    #         WHEN NOT MATCHED THEN INSERT BY NAME;
    #         """
    #         )
    #         cursor.commit()

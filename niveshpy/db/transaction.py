"""Transaction service for managing user transactions."""

from collections.abc import Iterable
import itertools
from typing import Literal, overload
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

from niveshpy.models.transaction import TransactionRead, TransactionWrite


class TransactionRepository:
    """Repository for managing transactions."""

    _table_name = "transactions"

    _column_mappings = {
        ast.Field.ACCOUNT: ["accounts.name", "accounts.institution"],
        ast.Field.AMOUNT: ["t.amount"],
        ast.Field.DATE: ["t.transaction_date"],
        ast.Field.DESCRIPTION: ["t.description"],
        ast.Field.SECURITY: [
            "securities.key",
            "securities.name",
            "securities.type",
            "securities.category",
        ],
        ast.Field.TYPE: ["t.type"],
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

    @overload
    def search_transactions(
        self,
        options: QueryOptions = ...,
        format: Literal[ResultFormat.POLARS] = ...,
    ) -> pl.DataFrame: ...

    @overload
    def search_transactions(
        self,
        options: QueryOptions = ...,
        format: Literal[ResultFormat.LIST] = ...,
    ) -> Iterable[TransactionRead]: ...

    def search_transactions(
        self,
        options: QueryOptions = DEFAULT_QUERY_OPTIONS,
        format: Literal[ResultFormat.POLARS, ResultFormat.LIST] = ResultFormat.POLARS,
    ) -> pl.DataFrame | Iterable[TransactionRead]:
        """Search for transactions matching the query options."""
        query = f"""
        SELECT t.id, t.transaction_date, t.type, t.description, t.amount, t.units, 
        concat(securities.name, ' (', securities.key, ')') AS security,
        concat(accounts.name, ' (', accounts.institution, ')') AS account,
        t.created_at AS created, t.metadata
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

        query += " ORDER BY t.transaction_date DESC, t.created_at DESC"
        if options.limit:
            query += " LIMIT ?"
            params.append(options.limit)
        query += ";"
        logger.debug("Executing search query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            cursor.execute(query, params)
            if format == ResultFormat.POLARS:
                return cursor.pl()
            else:
                return itertools.starmap(TransactionRead, cursor.fetchall())

    def insert_single_transaction(self, transaction: TransactionWrite) -> int | None:
        """Insert a single transaction into the database."""
        query = f"""
        INSERT INTO {self._table_name} 
        (transaction_date, type, description, amount, units, account_id, security_key, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id;
        """
        params = (
            transaction.transaction_date,
            transaction.type,
            transaction.description,
            transaction.amount,
            transaction.units,
            transaction.account_id,
            transaction.security_key,
            transaction.metadata,
        )
        logger.debug("Executing insert query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            cursor.begin()
            cursor.execute(query, params)
            res = cursor.fetchone()
            cursor.commit()
            return res[0] if res is not None else None

"""Transaction service for managing user transactions."""

import datetime
import itertools
from collections.abc import Iterable
from dataclasses import asdict
from typing import Literal, overload

import polars as pl

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.db.database import Database
from niveshpy.db.query import (
    DEFAULT_QUERY_OPTIONS,
    QueryOptions,
    ResultFormat,
    prepare_query_filters,
)
from niveshpy.models.account import AccountRead
from niveshpy.models.security import SecurityRead
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

    def get_transaction(self, transaction_id: int) -> TransactionRead | None:
        """Get a single transaction by its ID."""
        query = f"""
        SELECT t.id, t.transaction_date, t.type, t.description, t.amount, t.units,
        concat(securities.name, ' (', securities.key, ')') AS security,
        concat(accounts.name, ' (', accounts.institution, ')') AS account,
        t.created_at AS created, t.metadata
        FROM {self._table_name} t
        INNER JOIN securities ON t.security_key = securities.key
        INNER JOIN accounts ON t.account_id = accounts.id
        WHERE t.id = ?;
        """
        params = (transaction_id,)
        logger.debug("Executing get query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row is None:
                return None
            return TransactionRead(*row)

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

    def insert_multiple_transactions(
        self,
        transactions: list[TransactionWrite],
        accounts: list[AccountRead],
        securities: list[SecurityRead],
        date_range: tuple[datetime.date, datetime.date],
    ) -> list[TransactionRead]:
        """Insert multiple transactions into the database."""
        with self._db.cursor() as cursor:
            cursor.begin()
            cursor.register(
                "new_transactions",
                pl.from_dicts(
                    map(asdict, transactions),
                ),
            )
            cursor.register(
                "current_accounts",
                pl.from_dicts(
                    [asdict(acc) for acc in accounts],
                ),
            )
            cursor.register(
                "current_securities",
                pl.from_dicts(
                    [asdict(sec) for sec in securities],
                ),
            )
            # Delete existing transactions in the date range for the given accounts and securities
            delete_query = f"""
            DELETE FROM {self._table_name}
            WHERE transaction_date BETWEEN ? AND ?
            AND account_id IN (
                SELECT id FROM current_accounts
            )
            AND security_key IN (
                SELECT key FROM current_securities
            );
            """
            cursor.execute(delete_query, date_range)

            # Validate transactions before inserting
            cursor.execute(
                """SELECT COUNT(*) FROM new_transactions nt
                LEFT JOIN current_accounts ca ON nt.account_id = ca.id
                LEFT JOIN current_securities cs ON nt.security_key = cs.key
                WHERE ca.id IS NULL OR cs.key IS NULL;
                """
            )
            check_res = cursor.fetchone()
            invalid_count: int = check_res[0] if check_res else 0
            if invalid_count > 0:
                cursor.rollback()
                raise ValueError(
                    f"Found {invalid_count} transactions with invalid account IDs or security keys."
                )

            # Insert new transactions
            insert_query = f"""
            INSERT INTO {self._table_name}
            (transaction_date, type, description, amount, units, account_id, security_key, metadata)
            SELECT nt.transaction_date, nt.type, nt.description, nt.amount, nt.units,
            nt.account_id, nt.security_key, nt.metadata
            FROM new_transactions nt
            RETURNING *;
            """
            cursor.execute(insert_query)
            res = cursor.fetchall()
            cursor.commit()
            return [TransactionRead(*data) for data in res]

    def delete_transaction(self, transaction_id: int) -> bool:
        """Delete a transaction by its ID.

        Returns True if a transaction was deleted, False otherwise.
        """
        query = f"DELETE FROM {self._table_name} WHERE id = ? RETURNING *;"
        params = (transaction_id,)
        logger.debug("Executing delete query: %s with params: %s", query, params)

        with self._db.cursor() as cursor:
            cursor.begin()
            cursor.execute(query, params)
            res = cursor.fetchone()
            cursor.commit()
            return res is not None

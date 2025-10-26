"""Transaction service for managing user transactions."""

from collections.abc import Iterable
import datetime
import decimal
import itertools
from niveshpy.core.query import ast
from niveshpy.core.query.parser import QueryParser
from niveshpy.core.query.prepare import prepare_filters
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.db.query import QueryOptions, ResultFormat
from niveshpy.db.repositories import RepositoryContainer
import polars as pl
from niveshpy.core.logging import logger
from niveshpy.models.transaction import (
    TransactionRead,
    TransactionType,
    TransactionWrite,
)
from niveshpy.services.result import (
    InsertResult,
    ListResult,
    MergeAction,
    ResolutionStatus,
    SearchResolution,
)


class TransactionService:
    """Service handler for the transactions command group."""

    def __init__(self, repos: RepositoryContainer):
        """Initialize the TransactionService with repositories."""
        self._repos = repos

    def list_transactions(
        self,
        queries: tuple[str, ...],
        limit: int = 30,
    ) -> ListResult[pl.DataFrame]:
        """List transactions matching the query."""
        if limit < 1:
            logger.debug("Received non-positive limit: %d", limit)
            raise ValueError("Limit must be positive.")

        stripped_queries = map(str.strip, queries)
        lexers = map(QueryLexer, stripped_queries)
        parsers = map(QueryParser, lexers)
        filters: Iterable[ast.FilterNode] = itertools.chain.from_iterable(
            map(QueryParser.parse, parsers)
        )
        filters = prepare_filters(filters, ast.Field.SECURITY)
        logger.debug("Prepared filters: %s", filters)

        options = QueryOptions(
            filters=filters,
            limit=limit,
        )

        N = self._repos.transaction.count_transactions(options)
        if N == 0:
            return ListResult(pl.DataFrame(), 0)

        res = self._repos.transaction.search_transactions(options, ResultFormat.POLARS)
        return ListResult(res, N)

    def add_transaction(
        self,
        transaction_date: datetime.date,
        transaction_type: TransactionType,
        description: str,
        amount: decimal.Decimal,
        units: decimal.Decimal,
        account_id: int,
        security_key: str,
        source: str | None = None,
    ) -> InsertResult[int]:
        """Add a single transaction to the database."""
        if source:
            metadata = {"source": source}
        else:
            metadata = {}

        # Validate account and security exists
        account = self._repos.account.get_account(account_id)
        if account is None:
            raise ValueError(f"Account with ID {account_id} does not exist.")

        security = self._repos.security.get_security(security_key)
        if security is None:
            raise ValueError(f"Security with key {security_key} does not exist.")

        transaction = TransactionWrite(
            transaction_date=transaction_date,
            type=transaction_type,
            description=description,
            amount=amount,
            units=units,
            account_id=account_id,
            security_key=security_key,
            metadata=metadata,
        )

        txn_id = self._repos.transaction.insert_single_transaction(transaction)
        if txn_id is None:
            raise RuntimeError("Failed to insert new transaction.")
        return InsertResult(MergeAction.INSERT, txn_id)

    def get_account_choices(self) -> list[dict[str, str | int]]:
        """Get a list of accounts for selection."""
        accounts = self._repos.account.search_accounts(
            QueryOptions(limit=10_000), ResultFormat.LIST
        )
        return [
            {"value": account[0], "name": f"{account[0]}: {account[1]} ({account[2]})"}
            for account in accounts
        ]

    def get_security_choices(self) -> list[dict[str, str]]:
        """Get a list of securities for selection."""
        securities = self._repos.security.search_securities(
            QueryOptions(limit=10_000), ResultFormat.LIST
        )
        return [
            {"value": security[0], "name": f"{security[1]} ({security[0]})"}
            for security in securities
        ]

    def resolve_transaction(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> SearchResolution[TransactionRead]:
        """Resolve a query to a Transaction object if it exists.

        Logic:
        - If the queries are empty:
            - If `allow_ambiguous` is False, return NOT_FOUND.
            - Else return AMBIGUOUS with no candidates.
        - If the queries match exactly one account id, return EXACT with that account.
        - Else If `allow_ambiguous` is false, return NOT_FOUND.
        - Else perform a text search:
            - 0 matches: return NOT_FOUND
            - 1 match: return EXACT with that account
            - >1 matches: return AMBIGUOUS with the list of candidates
        """
        if not queries:
            if not allow_ambiguous:
                return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)

            # Return top `limit` transactions as candidates
            options = QueryOptions(limit=limit)
            transactions = self._repos.transaction.search_transactions(
                options, ResultFormat.LIST
            )
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=list(transactions),
                queries=queries,
            )

        # First, try to find an exact match by id
        transaction_id = (
            int(queries[0].strip()) if queries[0].strip().isdigit() else None
        )
        if transaction_id is not None:
            exact_transaction = self._repos.transaction.get_transaction(transaction_id)
            if exact_transaction:
                return SearchResolution(
                    status=ResolutionStatus.EXACT,
                    exact=exact_transaction,
                    queries=queries,
                )

        if not allow_ambiguous:
            # If ambiguous results are not allowed, return NOT_FOUND
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)

        # Perform a text search for candidates
        stripped_queries = map(str.strip, queries)
        lexers = map(QueryLexer, stripped_queries)
        parsers = map(QueryParser, lexers)
        filters: Iterable[ast.FilterNode] = itertools.chain.from_iterable(
            map(QueryParser.parse, parsers)
        )
        filters = prepare_filters(filters, ast.Field.SECURITY)

        options = QueryOptions(filters=filters, limit=limit)
        res = list(
            self._repos.transaction.search_transactions(options, ResultFormat.LIST)
        )
        if not res:
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)
        elif len(res) == 1:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=res[0],
                queries=queries,
            )
        else:
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=res,
                queries=queries,
            )
            # If we reach here, it means we have ambiguous results

    def delete_transaction(self, transaction_id: int) -> bool:
        """Delete a transaction by its ID."""
        return self._repos.transaction.delete_transaction(transaction_id)

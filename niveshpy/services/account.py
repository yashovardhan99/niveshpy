"""Account service for managing investment accounts."""

import itertools
from collections.abc import Iterable

import polars as pl

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.parser import QueryParser
from niveshpy.core.query.prepare import prepare_filters
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.db.query import QueryOptions, ResultFormat
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.models.account import AccountRead, AccountWrite
from niveshpy.services.result import (
    InsertResult,
    ListResult,
    MergeAction,
    ResolutionStatus,
    SearchResolution,
)


class AccountService:
    """Service handler for the accounts command group."""

    def __init__(self, repos: RepositoryContainer):
        """Initialize the AccountService with repositories."""
        self._repos = repos

    def list_accounts(
        self, queries: tuple[str, ...], limit: int = 30
    ) -> ListResult[pl.DataFrame]:
        """List accounts, optionally filtered by a query string."""
        stripped_queries = map(str.strip, queries)
        lexers = map(QueryLexer, stripped_queries)
        parsers = map(QueryParser, lexers)
        filters: Iterable[ast.FilterNode] = itertools.chain.from_iterable(
            map(QueryParser.parse, parsers)
        )
        filters = prepare_filters(filters, ast.Field.ACCOUNT)
        logger.debug("Prepared filters: %s", filters)

        options = QueryOptions(filters=filters, limit=limit)

        if limit < 1:
            logger.debug("Received non-positive limit: %d", limit)
            raise ValueError("Limit must be positive.")

        N = self._repos.account.count_accounts(options)
        if N == 0:
            return ListResult(pl.DataFrame(), 0)

        res = self._repos.account.search_accounts(
            options, format=ResultFormat.POLARS
        ).rename({"created_at": "created"})
        return ListResult(res, N)

    def add_account(
        self, name: str, institution: str, source: str | None = None
    ) -> InsertResult[AccountRead]:
        """Add a new account."""
        if not name.strip() or not institution.strip():
            raise ValueError("Account name and institution cannot be empty.")

        if source:
            metadata = {"source": source}
        else:
            metadata = {}
        account = AccountWrite(
            name=name.strip(), institution=institution.strip(), metadata=metadata
        )
        existing_account = self._repos.account.find_account(account)
        if existing_account is not None:
            logger.debug("Account already exists: %s", existing_account)
            return InsertResult(MergeAction.NOTHING, existing_account)
        new_account = self._repos.account.insert_single_account(account)
        if new_account is None:
            raise RuntimeError("Failed to insert new account.")
        logger.debug("Inserted new account with ID: %s", new_account.id)
        return InsertResult(MergeAction.INSERT, new_account)

    def resolve_account_id(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> SearchResolution[AccountRead]:
        """Resolve an account id to an Account object if it exists.

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

            # Return top `limit` accounts as candidates
            options = QueryOptions(limit=limit)
            res = self._repos.account.search_accounts(options, ResultFormat.LIST)
            accounts = [AccountRead(*row) for row in res] if res else []
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=accounts,
                queries=queries,
            )

        # First, try to find an exact match by id
        account_id = int(queries[0].strip()) if queries[0].strip().isdigit() else None
        if account_id is not None:
            exact_account = self._repos.account.get_account(account_id)
            if exact_account:
                return SearchResolution(
                    status=ResolutionStatus.EXACT,
                    exact=exact_account,
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
        filters = prepare_filters(filters, ast.Field.ACCOUNT)

        options = QueryOptions(filters=filters, limit=limit)
        res = self._repos.account.search_accounts(options, ResultFormat.LIST)
        if not res:
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)
        elif len(res) == 1:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=AccountRead(*res[0]),
                queries=queries,
            )
        else:
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=[AccountRead(*row) for row in res],
                queries=queries,
            )
            # If we reach here, it means we have ambiguous results

    def delete_account(self, account_id: int) -> bool:
        """Delete an account by its ID."""
        return self._repos.account.delete_account(account_id) is not None

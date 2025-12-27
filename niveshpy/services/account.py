"""Account service for managing investment accounts."""

import itertools
from collections.abc import Iterable, Sequence

from sqlmodel import select

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.parser import QueryParser
from niveshpy.core.query.prepare import (
    get_filters_from_queries_v2,
    prepare_filters,
)
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.database import session
from niveshpy.db.query import QueryOptions, ResultFormat
from niveshpy.db.repositories import RepositoryContainer
from niveshpy.models.account import Account, AccountCreate, AccountRead
from niveshpy.services.result import (
    InsertResult,
    MergeAction,
    ResolutionStatus,
    SearchResolution,
)


class AccountServiceV2:
    """Service handler for the accounts command group."""

    _column_mappings: dict[ast.Field, list[str]] = {
        ast.Field.ACCOUNT: ["name", "institution"],
    }

    def list_accounts(
        self, queries: tuple[str, ...], limit: int = 30, offset: int = 0
    ) -> Sequence[Account]:
        """List accounts, optionally filtered by a query string."""
        where_clause = get_filters_from_queries_v2(
            queries, ast.Field.ACCOUNT, self._column_mappings
        )

        with session() as sql_session:
            accounts = sql_session.exec(
                select(Account).where(*where_clause).offset(offset).limit(limit)
            ).all()
            return accounts

    def add_account(
        self, name: str, institution: str, source: str | None = None
    ) -> InsertResult[Account]:
        """Add a new account."""
        if not name.strip() or not institution.strip():
            raise ValueError("Account name and institution cannot be empty.")
        if source:
            properties = {"source": source}
        else:
            properties = {}
        account = AccountCreate(
            name=name.strip(), institution=institution.strip(), properties=properties
        )
        # Check for existing account
        query = select(Account).where(
            (Account.name == account.name)
            & (Account.institution == account.institution)
        )
        with session() as sql_session:
            existing_account = sql_session.exec(query).first()
            if existing_account is not None:
                logger.debug("Account already exists: %s", existing_account)
                return InsertResult(MergeAction.NOTHING, existing_account)

            # Otherwise, insert new account
            new_account = Account.model_validate(account)
            sql_session.add(new_account)
            sql_session.commit()
            sql_session.refresh(new_account)
            logger.debug("Inserted new account with ID: %s", new_account.id)
            return InsertResult(MergeAction.INSERT, new_account)


class AccountService:
    """Service handler for the accounts command group."""

    def __init__(self, repos: RepositoryContainer):
        """Initialize the AccountService with repositories."""
        self._repos = repos

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

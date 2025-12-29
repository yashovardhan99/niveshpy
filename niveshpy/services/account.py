"""Account service for managing investment accounts."""

from collections.abc import Sequence

from sqlmodel import select

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import (
    get_filters_from_queries,
)
from niveshpy.database import get_session
from niveshpy.models.account import Account, AccountCreate, AccountPublic
from niveshpy.services.result import (
    InsertResult,
    MergeAction,
    ResolutionStatus,
    SearchResolution,
)


class AccountService:
    """Service handler for the accounts command group."""

    _column_mappings: dict[ast.Field, list[str]] = {
        ast.Field.ACCOUNT: ["name", "institution"],
    }

    def list_accounts(
        self, queries: tuple[str, ...], limit: int = 30, offset: int = 0
    ) -> Sequence[AccountPublic]:
        """List accounts, optionally filtered by a query string."""
        where_clause = get_filters_from_queries(
            queries, ast.Field.ACCOUNT, self._column_mappings
        )

        with get_session() as session:
            accounts = session.exec(
                select(Account).where(*where_clause).offset(offset).limit(limit)
            ).all()
            return list(map(AccountPublic.model_validate, accounts))

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
        with get_session() as session:
            existing_account = session.exec(query).first()
            if existing_account is not None:
                logger.debug("Account already exists: %s", existing_account)
                return InsertResult(MergeAction.NOTHING, existing_account)

            # Otherwise, insert new account
            new_account = Account.model_validate(account)
            session.add(new_account)
            session.commit()
            session.refresh(new_account)
            logger.debug("Inserted new account with ID: %s", new_account.id)
            return InsertResult(MergeAction.INSERT, new_account)

    def resolve_account_id(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> SearchResolution[AccountPublic]:
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
            query = select(Account).limit(limit)
            with get_session() as session:
                accounts = list(
                    map(AccountPublic.model_validate, session.exec(query).all())
                )
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=accounts,
                queries=queries,
            )

        # First, try to find an exact match by id
        account_id = int(queries[0].strip()) if queries[0].strip().isdigit() else None
        if account_id is not None:
            with get_session() as session:
                exact_account = session.get(Account, account_id)
            if exact_account:
                return SearchResolution(
                    status=ResolutionStatus.EXACT,
                    exact=AccountPublic.model_validate(exact_account),
                    queries=queries,
                )

        if not allow_ambiguous:
            # If ambiguous results are not allowed, return NOT_FOUND
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)

        # Perform a text search for candidates
        accounts = list(self.list_accounts(queries, limit=limit))
        if not accounts:
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)
        elif len(accounts) == 1:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=accounts[0],
                queries=queries,
            )
        else:
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=accounts,
                queries=queries,
            )
            # If we reach here, it means we have ambiguous results

    def delete_account(self, account_id: int) -> bool:
        """Delete an account."""
        with get_session() as session:
            account = session.get(Account, account_id)
            if account is None:
                logger.debug("Account not found for deletion: %s", account_id)
                return False
            session.delete(account)
            session.commit()
            logger.debug("Deleted account with ID: %s", account_id)
            return True

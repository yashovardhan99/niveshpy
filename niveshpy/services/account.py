"""Account service for managing investment accounts."""

from collections.abc import Sequence

from sqlmodel import col, select

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import (
    get_filters_from_queries,
)
from niveshpy.database import get_session
from niveshpy.exceptions import AmbiguousResourceError, InvalidInputError
from niveshpy.models.account import Account, AccountCreate, AccountPublic
from niveshpy.services.result import (
    InsertResult,
    MergeAction,
)


class AccountService:
    """Service handler for the accounts command group."""

    _column_mappings: dict[ast.Field, list[str]] = {
        ast.Field.ACCOUNT: ["name", "institution"],
    }

    def list_accounts(
        self, queries: tuple[str, ...], limit: int = 30, offset: int = 0
    ) -> Sequence[AccountPublic]:
        """List accounts, optionally filtered by a query string.

        Args:
            queries (tuple[str, ...]): Query strings to filter accounts.
            limit (int): Maximum number of accounts to return.
            offset (int): Number of accounts to skip from the start.

        Returns:
            Sequence[AccountPublic]: List of accounts matching the query.

        Raises:
            InvalidInputError: If limit is less than 1 or offset is negative.
        """
        if limit < 1:
            raise InvalidInputError(limit, "Limit must be positive.")
        if offset < 0:
            raise InvalidInputError(offset, "Offset cannot be negative.")

        where_clause = get_filters_from_queries(
            queries, ast.Field.ACCOUNT, self._column_mappings
        )

        with get_session() as session:
            accounts = session.exec(
                select(Account)
                .where(*where_clause)
                .offset(offset)
                .limit(limit)
                .order_by(col(Account.id))
            ).all()
            return list(map(AccountPublic.model_validate, accounts))

    def add_account(
        self, name: str, institution: str, source: str | None = None
    ) -> InsertResult[Account]:
        """Add a new account."""
        if not name.strip() or not institution.strip():
            raise InvalidInputError(
                (name, institution), "Account name and institution cannot be empty."
            )
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
    ) -> Sequence[AccountPublic]:
        """Resolve an account id to an Account object if it exists.

        Args:
            queries (tuple): Tuple of query strings.
            limit (int): Maximum number of candidates to return.
            allow_ambiguous (bool): Whether to allow ambiguous results.

        Returns:
            Sequence[AccountPublic]: The resolved account(s).

        Raises:
            InvalidInputError: If no queries are provided and ambiguous results are not allowed.
            AmbiguousResourceError: If a direct match is not found and ambiguous results are not allowed.
        """
        # If no queries and ambiguous results not allowed, raise error
        if not queries and not allow_ambiguous:
            raise InvalidInputError(
                queries,
                "No queries provided to resolve account ID. Ambiguous results are not allowed.",
            )

        # Try to interpret query as account ID
        account_id = (
            int(queries[0].strip())
            if len(queries) == 1  # If there is exactly one query
            and queries[0].strip().isdigit()  # And it is a digit
            else None
        )
        # If we have a valid account ID
        if account_id is not None:
            with get_session() as session:
                exact_account = session.get(Account, account_id)
                if exact_account is not None:
                    return [AccountPublic.model_validate(exact_account)]

        # No exact match found by ID
        # If ambiguous results are not allowed, raise error
        if not allow_ambiguous:
            raise AmbiguousResourceError("account", " ".join(queries))

        # Perform a text search for candidates
        return self.list_accounts(queries, limit=limit)

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

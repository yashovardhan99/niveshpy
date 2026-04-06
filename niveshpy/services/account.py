"""Account service for managing investment accounts."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import (
    get_prepared_filters_from_queries,
)
from niveshpy.exceptions import (
    AmbiguousResourceError,
    InvalidInputError,
    OperationError,
    QuerySyntaxError,
)
from niveshpy.models.account import Account
from niveshpy.repositories.account_repository import AccountRepository
from niveshpy.services.result import (
    InsertResult,
    MergeAction,
)


@dataclass(slots=True, frozen=True)
class AccountService:
    """Service handler for the accounts command group."""

    account_repository: AccountRepository = field(default_factory=AccountRepository)

    def list_accounts(
        self, queries: tuple[str, ...], limit: int = 30, offset: int = 0
    ) -> Sequence[Account]:
        """List accounts, optionally filtered by a query string.

        Args:
            queries (tuple[str, ...]): Query strings to filter accounts.
            limit (int): Maximum number of accounts to return.
            offset (int): Number of accounts to skip from the start.

        Returns:
            Sequence[AccountPublic]: List of accounts matching the query.

        Raises:
            InvalidInputError: If limit is less than 1 or offset is negative.
            QuerySyntaxError: If the query strings cannot be parsed into valid filters.
        """
        if limit < 1:
            raise InvalidInputError(limit, "Limit must be positive.")
        if offset < 0:
            raise InvalidInputError(offset, "Offset cannot be negative.")

        filters = get_prepared_filters_from_queries(queries, ast.Field.ACCOUNT)

        try:
            accounts = self.account_repository.find_accounts(
                filters, limit=limit, offset=offset
            )
            return accounts
        except QuerySyntaxError as e:
            e.add_note(f"Caused by input queries: {' '.join(queries)}")
            raise QuerySyntaxError(" ".join(queries), e.cause) from e

    def add_account(
        self, name: str, institution: str, source: str | None = None
    ) -> InsertResult[int]:
        """Add a new account."""
        if not name.strip() or not institution.strip():
            raise InvalidInputError(
                (name, institution), "Account name and institution cannot be empty."
            )
        if source:
            properties = {"source": source}
        else:
            properties = {}
        account = Account(
            name=name.strip(), institution=institution.strip(), properties=properties
        )
        account_id = self.account_repository.insert_account(account)
        if account_id is not None:
            return InsertResult(MergeAction.INSERT, account_id)
        else:
            logger.debug("Account already exists; Fetching existing account ID.")
            existing_account = (
                self.account_repository.get_account_by_name_and_institution(
                    account.name, account.institution
                )
            )
            if existing_account is not None and existing_account.id is not None:
                return InsertResult(MergeAction.NOTHING, existing_account.id)
            else:
                raise OperationError("Failed to insert or fetch existing account ID.")

    def resolve_account_id(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> Sequence[Account]:
        """Resolve an account id to an Account object if it exists.

        Args:
            queries (tuple): Tuple of query strings.
            limit (int): Maximum number of candidates to return.
            allow_ambiguous (bool): Whether to allow ambiguous results.

        Returns:
            Sequence[Account]: The resolved account(s).

        Raises:
            InvalidInputError: If no queries are provided and ambiguous results are not allowed.
            AmbiguousResourceError: If a direct match is not found and ambiguous results are not allowed.
            QuerySyntaxError: If the query strings cannot be parsed into valid filters.
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
            exact_account = self.account_repository.get_account_by_id(account_id)
            if exact_account is not None:
                return [exact_account]

        # No exact match found by ID
        # If ambiguous results are not allowed, raise error
        if not allow_ambiguous:
            raise AmbiguousResourceError("account", " ".join(queries))

        # Perform a text search for candidates
        return self.list_accounts(queries, limit=limit)

    def delete_account(self, account_id: int) -> bool:
        """Delete an account."""
        if account_id < 1:
            raise InvalidInputError(
                account_id, "Account ID must be a positive integer."
            )
        return self.account_repository.delete_account_by_id(account_id)

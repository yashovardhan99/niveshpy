"""Transaction service for managing user transactions."""

import datetime
import decimal
from collections.abc import Sequence
from dataclasses import dataclass

from attrs import evolve

from niveshpy.core.query import ast
from niveshpy.core.query.prepare import (
    get_prepared_filters_from_queries,
)
from niveshpy.domain.repositories import (
    AccountRepository,
    SecurityRepository,
    TransactionRepository,
)
from niveshpy.domain.repositories.transaction_repository import (
    TransactionFetchProfile,
    TransactionSortOrder,
)
from niveshpy.domain.services import LotAccountingService
from niveshpy.exceptions import (
    AmbiguousResourceError,
    InvalidInputError,
    ResourceNotFoundError,
)
from niveshpy.models.transaction import (
    TransactionCreate,
    TransactionPublic,
    TransactionType,
)


@dataclass(slots=True, frozen=True)
class TransactionService:
    """Service handler for the transactions command group."""

    transaction_repository: TransactionRepository
    account_repository: AccountRepository
    security_repository: SecurityRepository
    lot_accounting_service: LotAccountingService

    def list_transactions(
        self,
        queries: tuple[str, ...],
        limit: int = 30,
        offset: int = 0,
        cost: bool = False,
    ) -> Sequence[TransactionPublic]:
        """List transactions matching the query."""
        if limit < 1:
            raise InvalidInputError(limit, "Limit must be positive.")
        if offset < 0:
            raise InvalidInputError(offset, "Offset cannot be negative.")

        if cost:
            # If cost is requested, we need to fetch all transactions matching the cost-related filters first,
            # compute their cost basis, and then filter the final results to those matching the original query.
            # This is necessary because cost basis computation may depend on the full transaction history of
            # relevant securities and accounts, which cannot be accurately determined from a limited query.
            cost_query_filters = get_prepared_filters_from_queries(
                queries,
                default_field=ast.Field.SECURITY,
                include_fields=[ast.Field.SECURITY, ast.Field.ACCOUNT],
            )
            all_transactions_for_cost = self.transaction_repository.find_transactions(
                cost_query_filters,
                fetch_profile=TransactionFetchProfile.MINIMAL,
                sort_order=TransactionSortOrder.DATE_ASC_ID_ASC,
            )

            transactions_with_cost = (
                self.lot_accounting_service.annotate_transactions_with_cost(
                    all_transactions_for_cost
                )
            )

        filters = get_prepared_filters_from_queries(
            queries, default_field=ast.Field.SECURITY
        )
        transactions = self.transaction_repository.find_transactions(
            filters,
            limit=limit,
            offset=offset,
            fetch_profile=TransactionFetchProfile.WITH_RELATIONS,
            sort_order=TransactionSortOrder.DATE_DESC_ID_ASC,
        )
        if cost:
            id_to_cost_transaction: dict[int, TransactionPublic] = {
                t.id: t for t in transactions_with_cost
            }
            transactions = [
                evolve(txn, cost=id_to_cost_transaction[txn.id].cost)
                for txn in transactions
            ]
        return transactions

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
    ) -> int:
        """Add a single transaction to the database."""
        if source:
            properties = {"source": source}
        else:
            properties = {}

        # Validate account and security exists
        account = self.account_repository.get_account_by_id(account_id)
        if account is None:
            raise ResourceNotFoundError("Account", account_id)
        security = self.security_repository.get_security_by_key(security_key)
        if security is None:
            raise ResourceNotFoundError("Security", security_key)

        transaction = TransactionCreate(
            transaction_date=transaction_date,
            type=transaction_type,
            description=description,
            amount=amount,
            units=units,
            account_id=account_id,
            security_key=security_key,
            properties=properties,
        )

        transaction_id = self.transaction_repository.insert_transaction(transaction)
        return transaction_id

    def get_account_choices(self) -> list[dict[str, str | int]]:
        """Get a list of accounts for selection."""
        accounts = self.account_repository.find_accounts([])
        return [
            {
                "value": str(account.id),
                "name": f"{account.id}: {account.name} ({account.institution})",
            }
            for account in accounts
        ]

    def get_security_choices(self) -> list[dict[str, str]]:
        """Get a list of securities for selection."""
        securities = self.security_repository.find_securities([])
        return [
            {"value": security.key, "name": f"{security.name} ({security.key})"}
            for security in securities
        ]

    def resolve_transaction(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> Sequence[TransactionPublic]:
        """Resolve a query to a Transaction object if it exists.

        Args:
            queries (tuple[str, ...]): The search queries.
            limit (int): The maximum number of candidates to return if ambiguous.
            allow_ambiguous (bool): Whether to allow ambiguous results.

        Returns:
            Sequence[TransactionPublic]: The resolved transaction(s).

        Raises:
            InvalidInputError: If no queries are provided and ambiguous results are not allowed.
            AmbiguousResourceError: If a direct match is not found and ambiguous results are not allowed
        """
        if not queries and not allow_ambiguous:
            raise InvalidInputError(
                queries,
                "No queries provided. Ambiguous results are not allowed.",
            )

        # Try to interpret the first query as a transaction ID
        transaction_id = (
            int(queries[0].strip())
            if len(queries) == 1 and queries[0].strip().isdigit()
            else None
        )
        # If we have a potential transaction ID, try to fetch it
        if transaction_id is not None:
            exact_transaction = self.transaction_repository.get_transaction_by_id(
                transaction_id
            )
            if exact_transaction is not None:
                return [exact_transaction]

        # No exact match found by ID
        # If ambiguous results are not allowed, raise error
        if not allow_ambiguous:
            raise AmbiguousResourceError("Transaction", " ".join(queries))

        # Perform a text search for candidates
        return self.list_transactions(queries, limit=limit)

    def delete_transaction(self, transaction_id: int) -> bool:
        """Delete a transaction by its ID."""
        return self.transaction_repository.delete_transaction_by_id(transaction_id)

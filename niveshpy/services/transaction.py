"""Transaction service for managing user transactions."""

import datetime
import decimal
from collections.abc import Sequence

from pydantic import RootModel
from sqlmodel import col, select

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_filters_from_queries
from niveshpy.database import get_session
from niveshpy.exceptions import (
    AmbiguousResourceError,
    InvalidInputError,
    ResourceNotFoundError,
)
from niveshpy.models.account import Account
from niveshpy.models.security import Security
from niveshpy.models.transaction import (
    TRANSACTION_COLUMN_MAPPING,
    Transaction,
    TransactionCreate,
    TransactionDisplay,
    TransactionPublicWithRelations,
    TransactionType,
)


class TransactionService:
    """Service handler for the transactions command group."""

    def list_transactions(
        self,
        queries: tuple[str, ...],
        limit: int = 30,
        offset: int = 0,
    ) -> Sequence[TransactionPublicWithRelations]:
        """List transactions matching the query."""
        if limit < 1:
            raise InvalidInputError(limit, "Limit must be positive.")
        if offset < 0:
            raise InvalidInputError(offset, "Offset cannot be negative.")

        where_clause = get_filters_from_queries(
            queries, ast.Field.SECURITY, TRANSACTION_COLUMN_MAPPING
        )
        with get_session() as session:
            transactions = session.exec(
                select(Transaction)
                .join(Security)
                .join(Account)
                .where(*where_clause)
                .offset(offset)
                .limit(limit)
                .order_by(col(Transaction.transaction_date).desc(), col(Transaction.id))
            ).all()
            return (
                RootModel[Sequence[TransactionPublicWithRelations]]
                .model_validate(transactions)
                .root
            )

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
    ) -> Transaction:
        """Add a single transaction to the database."""
        if source:
            properties = {"source": source}
        else:
            properties = {}

        # Validate account and security exists
        with get_session() as session:
            account = session.get(Account, account_id)
            security = session.get(Security, security_key)
        if account is None:
            raise ResourceNotFoundError("Account", account_id)
        if security is None:
            raise ResourceNotFoundError("Security", security_key)

        transaction = Transaction.model_validate(
            TransactionCreate(
                transaction_date=transaction_date,
                type=transaction_type,
                description=description,
                amount=amount,
                units=units,
                account_id=account_id,
                security_key=security_key,
                properties=properties,
            )
        )

        with get_session() as session:
            session.add(transaction)
            session.commit()
            session.refresh(transaction)
        return transaction

    def get_account_choices(self) -> list[dict[str, str | int]]:
        """Get a list of accounts for selection."""
        with get_session() as session:
            accounts = session.exec(select(Account).limit(10_000)).all()
        return [
            {
                "value": str(account.id),
                "name": f"{account.id}: {account.name} ({account.institution})",
            }
            for account in accounts
        ]

    def get_security_choices(self) -> list[dict[str, str]]:
        """Get a list of securities for selection."""
        with get_session() as session:
            securities = session.exec(select(Security).limit(10_000)).all()
        return [
            {"value": security.key, "name": f"{security.name} ({security.key})"}
            for security in securities
        ]

    def resolve_transaction(
        self, queries: tuple[str, ...], limit: int, allow_ambiguous: bool = True
    ) -> Sequence[TransactionDisplay]:
        """Resolve a query to a Transaction object if it exists.

        Args:
            queries (tuple[str, ...]): The search queries.
            limit (int): The maximum number of candidates to return if ambiguous.
            allow_ambiguous (bool): Whether to allow ambiguous results.

        Returns:
            Sequence[TransactionDisplay]: The resolved transaction(s).

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
            with get_session() as session:
                exact_transaction = session.get(Transaction, transaction_id)
                if exact_transaction is not None:
                    return [TransactionDisplay.model_validate(exact_transaction)]

        # No exact match found by ID
        # If ambiguous results are not allowed, raise error
        if not allow_ambiguous:
            raise AmbiguousResourceError("Transaction", " ".join(queries))

        # Perform a text search for candidates
        return [
            TransactionDisplay.model_validate(t)
            for t in self.list_transactions(queries, limit=limit)
        ]

    def delete_transaction(self, transaction_id: int) -> bool:
        """Delete a transaction by its ID."""
        with get_session() as session:
            transaction = session.get(Transaction, transaction_id)
            if transaction is None:
                logger.debug(
                    "Transaction with ID %d does not exist for deletion.",
                    transaction_id,
                )
                return False
            session.delete(transaction)
            session.commit()
            return True

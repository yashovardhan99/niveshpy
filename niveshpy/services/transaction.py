"""Transaction service for managing user transactions."""

import datetime
import decimal
from collections.abc import Sequence

from pydantic import RootModel
from sqlmodel import select

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_filters_from_queries_v2
from niveshpy.database import get_session
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
from niveshpy.services.result import (
    ResolutionStatus,
    SearchResolution,
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
            logger.debug("Received non-positive limit: %d", limit)
            raise ValueError("Limit must be positive.")

        where_clause = get_filters_from_queries_v2(
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
            raise ValueError(f"Account with ID {account_id} does not exist.")
        if security is None:
            raise ValueError(f"Security with key {security_key} does not exist.")

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
    ) -> SearchResolution[TransactionDisplay]:
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
            transactions = self.list_transactions(queries, limit=limit)
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=list(
                    RootModel[Sequence[TransactionDisplay]]
                    .model_validate(transactions)
                    .root
                ),
                queries=queries,
            )

        # First, try to find an exact match by id
        transaction_id = (
            int(queries[0].strip()) if queries[0].strip().isdigit() else None
        )
        if transaction_id is not None:
            with get_session() as session:
                exact_transaction = session.get(Transaction, transaction_id)
            if exact_transaction:
                return SearchResolution(
                    status=ResolutionStatus.EXACT,
                    exact=TransactionDisplay.model_validate(exact_transaction),
                    queries=queries,
                )

        if not allow_ambiguous:
            # If ambiguous results are not allowed, return NOT_FOUND
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)

        # Perform a text search for candidates
        res = self.list_transactions(queries, limit=limit)
        if not res:
            return SearchResolution(ResolutionStatus.NOT_FOUND, queries=queries)
        elif len(res) == 1:
            return SearchResolution(
                status=ResolutionStatus.EXACT,
                exact=TransactionDisplay.model_validate(res[0]),
                queries=queries,
            )
        else:
            return SearchResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=RootModel[Sequence[TransactionDisplay]]
                .model_validate(res)
                .root,
                queries=queries,
            )
            # If we reach here, it means we have ambiguous results

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

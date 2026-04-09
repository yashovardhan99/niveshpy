"""Pytest fixtures for service tests."""

import re
from collections.abc import Iterable, Sequence
from typing import Any

from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.domain.repositories.transaction_repository import (
    TransactionFetchProfile,
    TransactionSortOrder,
)
from niveshpy.exceptions import QuerySyntaxError, ResourceNotFoundError
from niveshpy.models.account import Account
from niveshpy.models.transaction import Transaction, TransactionCreate


class MockAccountRepository:
    """Mock implementation of AccountRepository for testing purposes."""

    def __init__(self):
        """Initialize the test account repository."""
        self._accounts = {}
        self._next_id = 1

    def get_account_by_id(self, account_id):
        """Retrieve an account by its ID."""
        return self._accounts.get(account_id)

    def get_account_by_name_and_institution(self, name, institution):
        """Retrieve an account by its name and institution."""
        for account in self._accounts.values():
            if account.name == name and account.institution == institution:
                return account
        return None

    def find_accounts(self, filters: Iterable[FilterNode], limit=None, offset=0):
        """Find accounts matching the given filters with optional pagination."""
        if not filters:
            return sorted(self._accounts.values(), key=lambda a: a.id)[
                offset : offset + limit if limit else None
            ]
        for filter in filters:
            if filter.field != Field.ACCOUNT:
                raise QuerySyntaxError(
                    str(filter), "Only 'Account' field is supported in filters."
                )

            result = set()

            # Get accounts by regex
            pattern = filter.value
            matching_accounts = [
                account.id
                for account in self._accounts.values()
                if re.search(str(pattern).lower(), account.name.lower())
                or re.search(str(pattern).lower(), account.institution.lower())
            ]
            result.update(matching_accounts)

        account_ids = sorted(result)[offset : offset + limit if limit else None]
        return [self._accounts[account_id] for account_id in account_ids]

    def find_accounts_by_name_and_institutions(self, names, institutions):
        """Find accounts matching the given name-institution pairs."""
        results = []
        pairs = set(zip(names, institutions, strict=True))
        for account in self._accounts.values():
            if (account.name, account.institution) in pairs:
                results.append(account)
        return results

    def insert_account(self, account):
        """Insert a new account into the repository."""
        if self.get_account_by_name_and_institution(account.name, account.institution):
            return None  # Simulate unique constraint violation by returning None
        account_id = self._next_id
        self._accounts[account_id] = Account(id=account_id, **account.model_dump())
        self._next_id += 1
        return account_id

    def insert_multiple_accounts(self, accounts):
        """Insert multiple accounts into the repository."""
        count = 0
        for account in accounts:
            account_id = self.insert_account(account)
            if account_id is not None:
                count += 1
        return count

    def delete_account_by_id(self, account_id):
        """Delete an account by its ID."""
        if account_id in self._accounts:
            self._accounts.pop(account_id)
            return True
        return False


class MockSecurityRepository:
    """Mock implementation of SecurityRepository for testing purposes."""

    def __init__(self):
        """Initialize the test security repository."""
        self._securities = {}

    def get_security_by_key(self, key):
        """Retrieve a security by its key."""
        return self._securities.get(key)

    def find_securities(self, filters: Iterable[FilterNode], limit=None, offset=0):
        """Find securities matching the given filters with optional pagination."""
        if not filters:
            return sorted(self._securities.values(), key=lambda a: a.key)[
                offset : offset + limit if limit else None
            ]
        else:
            raise NotImplementedError(
                "Filtering securities is not implemented in the mock repository."
            )

    def find_securities_by_keys(self, keys):
        """Find securities matching the given keys."""
        results = []
        for key in keys:
            security = self.get_security_by_key(key)
            if security:
                results.append(security)
        return results

    def insert_security(self, security):
        """Insert a new security into the repository."""
        if self.get_security_by_key(security.key):
            return False
        self._securities[security.key] = security
        return True

    def insert_multiple_securities(self, securities):
        """Insert multiple securities into the repository."""
        count = 0
        for security in securities:
            if self.insert_security(security):
                count += 1
        return count

    def delete_security_by_key(self, key):
        """Delete a security by its key."""
        if key in self._securities:
            self._securities.pop(key)
            return True
        return False

    def update_security_properties(
        self, security_key: str, *properties: tuple[str, Any]
    ) -> None:
        """Update properties of an existing security.

        Args:
            security_key: The unique key of the security to update.
            *properties: A variable number of tuples, each containing a property name and its new value.

        Raises:
            ResourceNotFoundError: If no security with the given key is found.
        """
        security = self.get_security_by_key(security_key)
        if not security:
            raise ResourceNotFoundError("Security", security_key)

        # Update properties
        for prop_name, prop_value in properties:
            security.properties[prop_name] = prop_value


class MockTransactionRepository:
    """Mock implementation of TransactionRepository for testing purposes."""

    def __init__(
        self,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
    ):
        """Initialize the test transaction repository."""
        self._transactions: dict[int, Transaction] = {}
        self._next_id: int = 1
        self._account_repository: MockAccountRepository = account_repository
        self._security_repository: MockSecurityRepository = security_repository

    def get_transaction_by_id(
        self,
        transaction_id: int,
        fetch_profile=TransactionFetchProfile.WITH_RELATIONS,
    ) -> Transaction | None:
        """Retrieve a transaction by its ID."""
        if fetch_profile == TransactionFetchProfile.WITH_RELATIONS:
            transaction = self._transactions.get(transaction_id)
            if transaction is None:
                return None
            # Simulate fetching related account and security
            account = self._account_repository.get_account_by_id(transaction.account_id)
            security = self._security_repository.get_security_by_key(
                transaction.security_key
            )
            # Return a new object with relations populated (simplified for testing)
            return transaction.model_copy(
                update={"account": account, "security": security}
            )
        else:
            return self._transactions.get(transaction_id)

    def find_transactions(
        self,
        filters: Iterable[FilterNode],
        limit=None,
        offset=0,
        fetch_profile=TransactionFetchProfile.WITH_RELATIONS,
        sort_order=TransactionSortOrder.DATE_DESC_ID_ASC,
    ) -> Sequence[Transaction]:
        """Find transactions matching the given filters with optional pagination."""
        if not filters:
            transaction_ids = self._transactions.keys()
            transactions = list(
                filter(
                    None,
                    [
                        self.get_transaction_by_id(tid, fetch_profile)
                        for tid in transaction_ids
                    ],
                )
            )
            if sort_order == TransactionSortOrder.DATE_DESC_ID_ASC:
                transactions.sort(
                    key=lambda t: (
                        (t.transaction_date, -t.id)
                        if t.id is not None
                        else (t.transaction_date, 0)
                    ),
                    reverse=True,
                )
            elif sort_order == TransactionSortOrder.DATE_ASC_ID_ASC:
                transactions.sort(
                    key=lambda t: (
                        (t.transaction_date, t.id)
                        if t.id is not None
                        else (t.transaction_date, 0)
                    )
                )
            elif sort_order == TransactionSortOrder.ID_ASC:
                transactions.sort(key=lambda t: t.id if t.id is not None else 0)
            elif sort_order == TransactionSortOrder.ID_DESC:
                transactions.sort(
                    key=lambda t: t.id if t.id is not None else 0, reverse=True
                )
            if limit is not None:
                return transactions[offset : offset + limit]
            else:
                return transactions[offset:]
        else:
            raise NotImplementedError(
                "Filtering transactions is not implemented in the mock repository."
            )

    def find_transactions_by_ids(
        self,
        ids: Sequence[int],
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
        sort_order: TransactionSortOrder = TransactionSortOrder.DATE_DESC_ID_ASC,
    ) -> Sequence[Transaction]:
        """Find transactions matching the given IDs."""
        results = []
        for transaction_id in ids:
            transaction = self.get_transaction_by_id(transaction_id, fetch_profile)
            if transaction:
                results.append(transaction)

        if sort_order == TransactionSortOrder.DATE_DESC_ID_ASC:
            results.sort(
                key=lambda t: (t.transaction_date, -t.id if t.id is not None else 0),
                reverse=True,
            )
        elif sort_order == TransactionSortOrder.DATE_ASC_ID_ASC:
            results.sort(
                key=lambda t: (t.transaction_date, t.id if t.id is not None else 0)
            )
        elif sort_order == TransactionSortOrder.ID_ASC:
            results.sort(key=lambda t: t.id if t.id is not None else 0)
        elif sort_order == TransactionSortOrder.ID_DESC:
            results.sort(key=lambda t: t.id if t.id is not None else 0, reverse=True)
        return results

    def insert_transaction(self, transaction: TransactionCreate) -> int:
        """Insert a new transaction into the repository."""
        transaction_id = self._next_id
        new_transaction = Transaction(id=transaction_id, **transaction.model_dump())
        self._transactions[transaction_id] = new_transaction
        self._next_id += 1
        return transaction_id

    def insert_multiple_transactions(
        self, transactions: Sequence[TransactionCreate]
    ) -> int:
        """Insert multiple transactions into the repository."""
        count = 0
        for transaction in transactions:
            self.insert_transaction(transaction)
            count += 1
        return count

    def delete_transaction_by_id(self, transaction_id):
        """Delete a transaction by its ID."""
        if transaction_id in self._transactions:
            self._transactions.pop(transaction_id)
            return True
        return False

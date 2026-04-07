"""Pytest fixtures for service tests."""

import re
from collections.abc import Iterable

from niveshpy.core.query.ast import Field, FilterNode
from niveshpy.exceptions import QuerySyntaxError
from niveshpy.models.account import Account


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

"""Pytest fixtures for service tests."""

import datetime
import re
from collections.abc import Iterable, Sequence
from typing import Any

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.domain.repositories.price_repository import PriceFetchProfile
from niveshpy.domain.repositories.transaction_repository import (
    TransactionFetchProfile,
    TransactionSortOrder,
)
from niveshpy.exceptions import (
    InvalidInputError,
    QuerySyntaxError,
    ResourceNotFoundError,
)
from niveshpy.models.account import Account
from niveshpy.models.price import Price, PriceCreate
from niveshpy.models.report import HoldingUnitRow
from niveshpy.models.security import Security
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

    def overwrite_transactions_in_date_range_for_accounts(
        self,
        transactions: Sequence[TransactionCreate],
        date_range: tuple[datetime.date, datetime.date],
        account_ids: Sequence[int],
    ) -> int:
        """Overwrite transactions for given accounts in a specified date range with new transactions."""
        start_date, end_date = date_range
        filtered_transactions = [
            transaction
            for transaction in transactions
            if transaction.account_id in account_ids
            and start_date <= transaction.transaction_date <= end_date
        ]

        if not filtered_transactions:
            return 0

        affected_account_ids = {
            transaction.account_id for transaction in filtered_transactions
        }
        transaction_ids_to_delete = [
            existing_transaction.id
            for existing_transaction in self._transactions.values()
            if existing_transaction.account_id in affected_account_ids
            and start_date <= existing_transaction.transaction_date <= end_date
        ]
        for transaction_id in transaction_ids_to_delete:
            self.delete_transaction_by_id(transaction_id)

        for transaction in filtered_transactions:
            self.insert_transaction(transaction)

        return len(filtered_transactions)

    def find_holding_units(
        self, filters: Iterable[FilterNode]
    ) -> Sequence[HoldingUnitRow]:
        """Find holding units matching the given filters."""
        raise NotImplementedError(
            "Finding holding units is not implemented in the mock repository."
        )


class MockPriceRepository:
    """Mock repository implementation for managing price data."""

    def __init__(self, security_repository: MockSecurityRepository):
        """Initialize the mock price repository."""
        self._prices: dict[str, dict[datetime.date, Price]] = {}
        self._security_repository = security_repository

    def get_price_by_key_and_date(
        self,
        security_key: str,
        date: datetime.date,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Price | None:
        """Fetch a price by its security key and date.

        Args:
            security_key: The key of the security to fetch the price for.
            date: The date for which to fetch the price.
            fetch_profile: The profile determining the level of detail to fetch for the price.

        Returns:
            The Price object if found, otherwise None.
        """
        return self._prices.get(security_key, {}).get(date)

    def _search_security_filter(
        self, filters: Iterable[FilterNode], securities: Sequence[Security]
    ) -> Sequence[Security]:
        """Helper method to search for a security in the filters and return the corresponding Security object if found."""
        for filter in filters:
            if filter.field == Field.SECURITY:
                return [
                    s
                    for s in securities
                    if re.search(str(filter.value).lower(), s.name.lower())
                    or re.search(str(filter.value).lower(), s.key.lower())
                    or re.search(str(filter.value).lower(), s.type.value.lower())
                    or re.search(str(filter.value).lower(), s.category.value.lower())
                ]
        return securities

    def _get_date_range(
        self, filters: Iterable[FilterNode]
    ) -> tuple[datetime.date | None, datetime.date | None]:
        """Helper method to extract the date range from the filters."""
        start_date = None
        end_date = None
        for filter in filters:
            print(f"DEBUG: Processing filter: {filter}")
            if filter.field == Field.DATE:
                if filter.operator in (
                    Operator.GREATER_THAN,
                    Operator.GREATER_THAN_EQ,
                ) and isinstance(filter.value, datetime.date):
                    start_date: datetime.date = filter.value
                elif filter.operator in (
                    Operator.LESS_THAN,
                    Operator.LESS_THAN_EQ,
                ) and isinstance(filter.value, datetime.date):
                    end_date: datetime.date = filter.value
                elif filter.operator == Operator.EQUALS and isinstance(
                    filter.value, datetime.date
                ):
                    start_date: datetime.date = filter.value
                    end_date: datetime.date = filter.value
                elif filter.operator == Operator.IN:
                    if isinstance(filter.value, Iterable):
                        dates = [
                            v for v in filter.value if isinstance(v, datetime.date)
                        ]
                        if dates:
                            start_date = min(dates)
                            end_date = max(dates)
        return start_date, end_date

    def find_all_prices(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Sequence[Price]:
        """Find all prices matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of Price objects matching the filters and pagination criteria.
        """
        securities = self._security_repository.find_securities([])
        securities = self._search_security_filter(filters, securities)
        price_dicts = [self._prices[s.key] for s in securities if s.key in self._prices]
        start_date, end_date = self._get_date_range(filters)
        print(f"DEBUG: start_date={start_date}, end_date={end_date}")
        prices = []
        for price_dict in price_dicts:
            for date, price in price_dict.items():
                if (start_date is None or date >= start_date) and (
                    end_date is None or date <= end_date
                ):
                    prices.append(price)
        prices.sort(key=lambda p: (p.date, p.security_key))
        return prices[offset : offset + limit if limit else None]

    def find_latest_prices(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Sequence[Price]:
        """Find the latest prices for securities matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of the latest Price objects for securities matching the filters and pagination criteria.
        """
        securities = self._security_repository.find_securities([])
        securities = self._search_security_filter(filters, securities)
        price_dicts = [self._prices[s.key] for s in securities if s.key in self._prices]
        latest_prices = []
        for price_dict in price_dicts:
            if price_dict:
                latest_date = max(price_dict.keys())
                latest_prices.append(price_dict[latest_date])
        latest_prices.sort(key=lambda p: (p.date, p.security_key))
        return latest_prices[offset : offset + limit if limit else None]

    def overwrite_price(self, price: PriceCreate) -> None:
        """Overwrite an existing price or insert a new one if it doesn't exist.

        Args:
            price: The PriceCreate object containing the price information to overwrite or insert.

        Raises:
            ResourceNotFoundError: If the associated security for the price does not exist in the database.
        """
        security = self._security_repository.get_security_by_key(price.security_key)
        if not security:
            raise ResourceNotFoundError(
                "Security", price.security_key, f"for price on {price.date}"
            )
        prices = self._prices.setdefault(price.security_key, {})
        prices[price.date] = Price(**price.model_dump(), security=security)

    def replace_prices_in_range(
        self,
        security_key: str,
        start_date: datetime.date,
        end_date: datetime.date,
        new_prices: Sequence[PriceCreate],
        batch_size: int | None = None,
    ) -> None:
        """Replace all prices for a given security within a specified date range with new prices.

        Args:
            security_key: The key of the security for which to replace prices.
            start_date: The start date of the range for which to replace prices (inclusive).
            end_date: The end date of the range for which to replace prices (inclusive).
            new_prices: A sequence of PriceCreate objects containing the new price information to insert.
            batch_size: Optional batch size for processing the replacement in chunks.
                If None, the replacement will be processed in a single batch.

        Raises:
            ResourceNotFoundError: If the given security key does not exist in the database.
            InvalidInputError: If any of the new prices have dates outside the specified date range,
            have a security key that does not match the given security key, or if there are duplicate
            dates in the new prices.
        """
        if start_date > end_date:
            raise InvalidInputError(
                (start_date, end_date),
                "Start date must be less than or equal to end date",
            )

        seen_dates: set[datetime.date] = set()
        """Set to track seen dates for validating that there are no duplicate dates in the new prices."""

        # Validate the batch of new prices before making any changes to the database
        for price in new_prices:
            if price.security_key != security_key:
                raise InvalidInputError(
                    price,
                    f"Price security key {price.security_key} does not match the given security key {security_key}",
                )
            if price.date < start_date or price.date > end_date:
                raise InvalidInputError(
                    price,
                    f"Price date {price.date} is outside the specified date range {start_date} to {end_date}",
                )
            if price.date in seen_dates:
                raise InvalidInputError(
                    price.date, "Duplicate price date found in new prices"
                )
            seen_dates.add(price.date)

            if price.high < max(price.low, price.open, price.close) or price.low > min(
                price.high, price.open, price.close
            ):
                raise InvalidInputError(
                    price,
                    "High price must be greater than or equal to low, open, and close prices, and low price must be less than or equal to high, open, and close prices",
                )

        security = self._security_repository.get_security_by_key(security_key)
        if not security:
            raise ResourceNotFoundError("Security", security_key)

        # If validation passes, proceed with replacing the prices in the database
        prices = self._prices.setdefault(security_key, {})
        # Remove existing prices in the specified date range
        for date in list(prices.keys()):
            if start_date <= date <= end_date:
                del prices[date]
        # Insert new prices
        for price in new_prices:
            prices[price.date] = Price(**price.model_dump(), security=security)

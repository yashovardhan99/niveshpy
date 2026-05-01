"""Pytest fixtures for service tests."""

import datetime
import re
from collections.abc import Iterable, Sequence
from typing import Any, Literal

from attrs import asdict, evolve

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
from niveshpy.models.account import AccountCreate, AccountPublic
from niveshpy.models.price import PriceCreate, PricePublic
from niveshpy.models.report import Allocation, HoldingUnitRow
from niveshpy.models.security import SecurityCreate, SecurityPublic
from niveshpy.models.transaction import TransactionCreate, TransactionPublic


class MockAccountRepository:
    """Mock implementation of AccountRepository for testing purposes."""

    def __init__(self):
        """Initialize the test account repository."""
        self._accounts: dict[int, AccountPublic] = {}
        self._next_id = 1

    def get_account_by_id(self, account_id: int) -> AccountPublic | None:
        """Retrieve an account by its ID."""
        return self._accounts.get(account_id)

    def get_account_by_name_and_institution(
        self, name: str, institution: str
    ) -> AccountPublic | None:
        """Retrieve an account by its name and institution."""
        for account in self._accounts.values():
            if account.name == name and account.institution == institution:
                return account
        return None

    def find_accounts(
        self, filters: Iterable[FilterNode], limit: int | None = None, offset: int = 0
    ) -> Sequence[AccountPublic]:
        """Find accounts matching the given filters with optional pagination."""
        if not filters:
            return sorted(self._accounts.values(), key=lambda account: account.id)[
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

        accounts = sorted(result, key=lambda account_id: account_id)[
            offset : offset + limit if limit else None
        ]
        return self.find_accounts_by_ids(accounts)

    def find_accounts_by_ids(
        self, account_ids: Sequence[int]
    ) -> Sequence[AccountPublic]:
        """Find accounts matching the given sequence of IDs.

        Args:
            account_ids: A sequence of account IDs to search for.

        Returns:
            A sequence of Account objects matching the given IDs.
        """
        results = []
        for account_id in account_ids:
            account = self.get_account_by_id(account_id)
            if account:
                results.append(account)
        return results

    def find_accounts_by_name_and_institutions(
        self, names: Sequence[str], institutions: Sequence[str]
    ) -> Sequence[AccountPublic]:
        """Find accounts matching the given name-institution pairs."""
        results = []
        pairs = set(zip(names, institutions, strict=True))
        for account in self._accounts.values():
            if (account.name, account.institution) in pairs:
                results.append(account)
        return results

    def insert_account(self, account: AccountCreate) -> int | None:
        """Insert a new account into the repository."""
        if self.get_account_by_name_and_institution(account.name, account.institution):
            return None  # Simulate unique constraint violation by returning None
        account_id = self._next_id
        self._accounts[account_id] = AccountPublic(
            id=account_id,
            name=account.name,
            institution=account.institution,
            properties=account.properties,
            created=datetime.datetime.now(),
        )
        self._next_id += 1
        return account_id

    def insert_multiple_accounts(self, accounts: Iterable[AccountCreate]) -> int:
        """Insert multiple accounts into the repository."""
        count = 0
        for account in accounts:
            account_id = self.insert_account(account)
            if account_id is not None:
                count += 1
        return count

    def delete_account_by_id(self, account_id: int) -> bool:
        """Delete an account by its ID."""
        if account_id in self._accounts:
            self._accounts.pop(account_id)
            return True
        return False


class MockSecurityRepository:
    """Mock implementation of SecurityRepository for testing purposes."""

    def __init__(self):
        """Initialize the test security repository."""
        self._securities: dict[str, SecurityPublic] = {}

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

    def insert_security(self, security: SecurityCreate):
        """Insert a new security into the repository."""
        if self.get_security_by_key(security.key):
            return False
        self._securities[security.key] = SecurityPublic(
            key=security.key,
            name=security.name,
            type=security.type,
            category=security.category,
            properties=security.properties,
            created=datetime.datetime.now(),
        )
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
            security = evolve(
                security, properties={**security.properties, prop_name: prop_value}
            )
        self._securities[security_key] = security


class MockTransactionRepository:
    """Mock implementation of TransactionRepository for testing purposes."""

    def __init__(
        self,
        account_repository: MockAccountRepository,
        security_repository: MockSecurityRepository,
        price_repository: "MockPriceRepository | None" = None,
    ):
        """Initialize the test transaction repository."""
        self._transactions: dict[int, TransactionPublic] = {}
        self._next_id: int = 1
        self._account_repository: MockAccountRepository = account_repository
        self._security_repository: MockSecurityRepository = security_repository
        self._price_repository: MockPriceRepository | None = price_repository

    def _matches_regex_filter(self, txn: TransactionPublic, filter: FilterNode) -> bool:
        """Check if a transaction matches a single REGEX_MATCH filter."""
        if filter.field == Field.SECURITY:
            security = self._security_repository.get_security_by_key(txn.security_key)
            if security is None:
                return False
            pattern = str(filter.value).lower()
            return bool(
                re.search(pattern, security.key.lower())
                or re.search(pattern, security.name.lower())
                or re.search(pattern, security.type.value.lower())
                or re.search(pattern, security.category.value.lower())
            )
        elif filter.field == Field.ACCOUNT:
            account = self._account_repository.get_account_by_id(txn.account_id)
            if account is None:
                return False
            pattern = str(filter.value).lower()
            return bool(
                re.search(pattern, account.name.lower())
                or re.search(pattern, account.institution.lower())
            )
        return True

    def _matches_filters(
        self, txn: TransactionPublic, filters: Iterable[FilterNode]
    ) -> bool:
        """Replicate get_sqlalchemy_filters AND/OR semantics.

        All REGEX_MATCH filters across all fields are OR'd into one condition.
        Non-REGEX_MATCH filters each become a separate AND condition.
        """
        filters = list(filters)
        regex_filters = [f for f in filters if f.operator == Operator.REGEX_MATCH]
        non_regex_filters = [f for f in filters if f.operator != Operator.REGEX_MATCH]

        # Non-regex filters: each must match (AND)
        for f in non_regex_filters:
            if f.field == Field.SECURITY:
                security = self._security_repository.get_security_by_key(
                    txn.security_key
                )
                if security is None:
                    return False
                values = f.value if isinstance(f.value, tuple) else (f.value,)
                if security.key not in values:
                    return False
            elif f.field == Field.ACCOUNT:
                account = self._account_repository.get_account_by_id(txn.account_id)
                if account is None:
                    return False
                values = f.value if isinstance(f.value, tuple) else (f.value,)
                if account.name not in values and account.institution not in values:
                    return False

        # Regex filters: at least one must match (OR)
        if regex_filters:
            if not any(self._matches_regex_filter(txn, f) for f in regex_filters):
                return False

        return True

    def get_transaction_by_id(
        self,
        transaction_id: int,
        fetch_profile=TransactionFetchProfile.WITH_RELATIONS,
    ) -> TransactionPublic | None:
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
            return evolve(
                transaction,
                account=account,
                security=security,
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
    ) -> Sequence[TransactionPublic]:
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
            transactions = [
                t
                for t in self._transactions.values()
                if self._matches_filters(t, filters)
            ]
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

    def find_transactions_by_ids(
        self,
        ids: Sequence[int],
        fetch_profile: TransactionFetchProfile = TransactionFetchProfile.WITH_RELATIONS,
        sort_order: TransactionSortOrder = TransactionSortOrder.DATE_DESC_ID_ASC,
    ) -> Sequence[TransactionPublic]:
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
        transaction_data = asdict(transaction, recurse=False)
        new_transaction = TransactionPublic(
            **transaction_data,
            id=transaction_id,
            created=datetime.datetime.now(),
        )
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
        from decimal import Decimal

        filters = list(filters)
        all_txns = list(self._transactions.values())
        if filters:
            all_txns = [t for t in all_txns if self._matches_filters(t, filters)]

        # Group by (security_key, account_id)
        groups: dict[tuple[str, int], list] = {}
        for txn in all_txns:
            key = (txn.security_key, txn.account_id)
            groups.setdefault(key, []).append(txn)

        rows = []
        for (security_key, account_id), txns in groups.items():
            total_units = sum((t.units for t in txns), Decimal(0))
            if total_units >= Decimal("0.001"):
                last_date = max(t.transaction_date for t in txns)
                rows.append(
                    HoldingUnitRow(
                        security_key=security_key,
                        account_id=account_id,
                        total_units=total_units,
                        last_transaction_date=last_date,
                    )
                )
        return rows

    def find_allocation(
        self,
        filters: Iterable[FilterNode],
        group_by: Literal["category", "type", "both"],
    ) -> Sequence[Allocation]:
        """Find allocations matching the given filters."""
        from collections import defaultdict
        from decimal import Decimal

        if self._price_repository is None:
            raise NotImplementedError(
                "find_allocation requires a price_repository to be set."
            )

        filters = list(filters)
        all_txns = list(self._transactions.values())
        if filters:
            all_txns = [t for t in all_txns if self._matches_filters(t, filters)]

        # Group by security_key only (aggregate across accounts)
        sec_groups: dict[str, list] = {}
        for txn in all_txns:
            sec_groups.setdefault(txn.security_key, []).append(txn)

        # Latest price filters: only SECURITY and DATE fields pass through
        price_filters = [f for f in filters if f.field in (Field.SECURITY, Field.DATE)]
        latest_prices = {
            p.security_key: p
            for p in self._price_repository.find_latest_prices(price_filters)
        }

        group_amounts: dict[tuple, Decimal] = defaultdict(Decimal)
        group_dates: dict[tuple, datetime.date] = {}

        for security_key, txns in sec_groups.items():
            total_units = sum((t.units for t in txns), Decimal(0))
            if total_units < Decimal("0.001"):
                continue
            price = latest_prices.get(security_key)
            if price is None:
                continue
            security = self._security_repository.get_security_by_key(security_key)
            if security is None:
                continue

            holding_value = total_units * price.close
            last_txn_date = max(t.transaction_date for t in txns)
            as_of = max(last_txn_date, price.date)

            if group_by == "both":
                key: tuple = (security.category, security.type)
            elif group_by == "type":
                key = (None, security.type)
            else:  # category
                key = (security.category, None)

            group_amounts[key] += holding_value
            group_dates[key] = (
                min(group_dates[key], as_of) if key in group_dates else as_of
            )

        if not group_amounts:
            return []

        total_value = sum(group_amounts.values())
        results = [
            Allocation(
                security_category=key[0],
                security_type=key[1],
                date=group_dates[key],
                amount=amount.quantize(Decimal("0.01")),
                allocation=(amount / total_value).quantize(Decimal("0.0001")),
            )
            for key, amount in group_amounts.items()
        ]
        results.sort(key=lambda a: a.amount, reverse=True)
        return results


class MockPriceRepository:
    """Mock repository implementation for managing price data."""

    def __init__(self, security_repository: MockSecurityRepository):
        """Initialize the mock price repository."""
        self._prices: dict[str, dict[datetime.date, PricePublic]] = {}
        self._security_repository = security_repository

    def get_price_by_key_and_date(
        self,
        security_key: str,
        date: datetime.date,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> PricePublic | None:
        """Fetch a price by its security key and date.

        Args:
            security_key: The key of the security to fetch the price for.
            date: The date for which to fetch the price.
            fetch_profile: The profile determining the level of detail to fetch for the price.

        Returns:
            The PricePublic object if found, otherwise None.
        """
        return self._prices.get(security_key, {}).get(date)

    def _search_security_filter(
        self, filters: Iterable[FilterNode], securities: Sequence[SecurityPublic]
    ) -> Sequence[SecurityPublic]:
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
    ) -> Sequence[PricePublic]:
        """Find all prices matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of PricePublic objects matching the filters and pagination criteria.
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
    ) -> Sequence[PricePublic]:
        """Find the latest prices for securities matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of the latest PricePublic objects for securities matching the filters and pagination criteria.
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
        prices[price.date] = PricePublic(
            security_key=price.security_key,
            security=security,
            open=price.open,
            high=price.high,
            low=price.low,
            close=price.close,
            date=price.date,
            properties=price.properties,
            created=datetime.datetime.now(),
        )

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
            prices[price.date] = PricePublic(
                security_key=price.security_key,
                security=security,
                open=price.open,
                high=price.high,
                low=price.low,
                close=price.close,
                date=price.date,
                properties=price.properties,
                created=datetime.datetime.now(),
            )

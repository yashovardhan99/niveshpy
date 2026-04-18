"""Service layer for generating financial reports."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from niveshpy.core.query.ast import Field
from niveshpy.core.query.prepare import get_prepared_filters_from_queries
from niveshpy.domain.repositories import (
    AccountRepository,
    PriceRepository,
    SecurityRepository,
    TransactionRepository,
)
from niveshpy.domain.repositories.price_repository import PriceFetchProfile
from niveshpy.domain.repositories.transaction_repository import (
    TransactionFetchProfile,
    TransactionSortOrder,
)
from niveshpy.domain.services import LotAccountingService
from niveshpy.exceptions import InvalidInputError
from niveshpy.models.report import Holding


@dataclass(slots=True, frozen=True)
class ReportService:
    """Service for generating various financial reports."""

    transaction_repository: TransactionRepository
    price_repository: PriceRepository
    security_repository: SecurityRepository
    account_repository: AccountRepository
    lot_accounting_service: LotAccountingService

    def get_holdings(
        self,
        queries: tuple[str, ...],
        limit: int,
        offset: int = 0,
    ) -> Sequence[Holding]:
        """Get a list of holdings based on the provided queries and pagination parameters."""
        if not limit >= 1:
            raise InvalidInputError(limit, "Limit must be at least 1")
        if not offset >= 0:
            raise InvalidInputError(offset, "Offset cannot be negative")

        filters = get_prepared_filters_from_queries(queries, Field.SECURITY)
        holding_unit_rows = self.transaction_repository.find_holding_units(filters)
        holding_unit_map = {
            (row.security_key, row.account_id): row for row in holding_unit_rows
        }
        if not holding_unit_rows:
            return []
        prices = {
            price.security_key: price
            for price in self.price_repository.find_latest_prices(
                [f for f in filters if f.field == Field.SECURITY],
                fetch_profile=PriceFetchProfile.MINIMAL,
            )
        }
        transactions = self.transaction_repository.find_transactions(
            filters,
            fetch_profile=TransactionFetchProfile.MINIMAL,
            sort_order=TransactionSortOrder.DATE_ASC_ID_ASC,
        )
        position_costs = self.lot_accounting_service.compute_position_costs(
            transactions
        )

        security_keys, account_ids = tuple(zip(*position_costs.keys(), strict=True))

        securities = self.security_repository.find_securities_by_keys(security_keys)
        security_map = {security.key: security for security in securities}
        accounts = self.account_repository.find_accounts_by_ids(account_ids)
        account_map = {account.id: account for account in accounts}

        holdings: list[Holding] = []
        for (security_key, account_id), cost in position_costs.items():
            holding_units_row = holding_unit_map.get((security_key, account_id))
            if not holding_units_row:
                continue  # This can happen if there are transactions but all units are sold off - skip these from holdings report
            price = prices.get(security_key)
            holdings.append(
                Holding(
                    security=security_map[security_key],
                    account=account_map[account_id],
                    date=max(holding_units_row.last_transaction_date, price.date)
                    if price
                    else holding_units_row.last_transaction_date,
                    units=holding_units_row.total_units,
                    invested=cost,
                    amount=(
                        holding_units_row.total_units * price.close if price else cost
                    ).quantize(Decimal("0.01")),
                )
            )
        # Sort by amount desc, then account id asc, then security key asc for deterministic pagination
        holdings.sort(key=lambda h: (-h.amount, h.account.id, h.security.key))
        return holdings[offset : offset + limit]

"""Service layer for generating financial reports."""

import datetime
import heapq
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from niveshpy.core.logging import logger
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
from niveshpy.exceptions import InvalidInputError, OperationError
from niveshpy.models.report import (
    Holding,
    PerformanceHolding,
    PerformanceResult,
    PortfolioTotals,
    SummaryResult,
)
from niveshpy.services.helpers import compute_xirr
from niveshpy.services.report import get_allocation


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
        limit: int | None = None,
        offset: int = 0,
    ) -> Sequence[Holding]:
        """Get a list of holdings based on the provided queries and pagination parameters."""
        if limit is not None and not limit >= 1:
            raise InvalidInputError(limit, "Limit must be at least 1")
        if not offset >= 0:
            raise InvalidInputError(offset, "Offset cannot be negative")

        filters = get_prepared_filters_from_queries(
            queries, Field.SECURITY, include_fields={Field.SECURITY, Field.ACCOUNT}
        )
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
        return (
            holdings[offset : offset + limit]
            if limit is not None
            else holdings[offset:]
        )

    def get_performance(
        self, queries: tuple[str, ...], limit: int | None = None, offset: int = 0
    ) -> PerformanceResult:
        """Get a list of holdings with performance metrics based on the provided queries and pagination parameters."""
        holdings = self.get_holdings(
            queries, limit=None
        )  # Get all holdings matching filters without pagination
        if not holdings:
            # Return empty performance result if there are no holdings -
            # this avoids unnecessary calculations and also ensures
            # we return zero totals instead of None for an empty portfolio
            return PerformanceResult(
                holdings=[],
                totals=PortfolioTotals(
                    Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), None, None
                ),
            )

        totals = self._compute_portfolio_totals(holdings)
        # We can apply pagination after computing totals since performance metrics
        # are based on the entire portfolio, not just the paginated subset

        holdings = (
            holdings[offset : offset + limit]
            if limit is not None
            else holdings[offset:]
        )
        if not holdings:
            return PerformanceResult(holdings=[], totals=totals)
            # If pagination parameters result in no holdings, return empty list
            # but still include totals for the entire portfolio

        filters = get_prepared_filters_from_queries(
            queries, Field.SECURITY, include_fields={Field.SECURITY, Field.ACCOUNT}
        )
        transactions = self.transaction_repository.find_transactions(
            filters,
            fetch_profile=TransactionFetchProfile.MINIMAL,
            sort_order=TransactionSortOrder.DATE_ASC_ID_ASC,
        )
        txn_groups = {}
        for txn in transactions:
            key = (txn.security_key, txn.account_id)
            txn_groups.setdefault(key, []).append(txn)

        try:
            totals.xirr = (
                compute_xirr(
                    transactions, totals.total_current_value, totals.last_updated
                )
                if transactions
                else None
            )
        except OperationError as exc:
            logger.warning("Could not compute portfolio XIRR: %s", exc)
            totals.xirr = None

        performance_holdings = []
        for holding in holdings:
            key = (holding.security.key, holding.account.id)
            holding_transactions = txn_groups.get(key, [])
            try:
                xirr = compute_xirr(holding_transactions, holding.amount, holding.date)
            except OperationError as exc:
                logger.warning(
                    "Could not compute XIRR for holding %s in account %s: %s",
                    holding.security.key,
                    holding.account.name,
                    exc,
                )
                xirr = None
            performance_holdings.append(PerformanceHolding.from_holding(holding, xirr))

        return PerformanceResult(holdings=performance_holdings, totals=totals)

    def get_summary(self, queries: tuple[str, ...], top_n: int = 5) -> SummaryResult:
        """Generate portfolio summary combining metrics, top holdings, and allocation."""
        logger.info("Generating portfolio summary (top_n=%d)", top_n)
        # Get all holdings and compute totals for summary metrics
        result = self.get_performance(queries)

        # Get top N holdings by current value for summary display
        top_holdings = heapq.nlargest(
            top_n, result.holdings, key=lambda h: h.current_value
        )

        # Get allocation by category for summary display (could also do by type or both if desired)
        allocation = get_allocation(queries, group_by="category")

        return SummaryResult(
            as_of=result.holdings[0].date if result.holdings else None,
            metrics=result.totals,  # PortfolioTotals already has everything
            top_holdings=top_holdings,
            allocation=allocation,
        )

    def _compute_portfolio_totals(self, holdings: Sequence[Holding]) -> PortfolioTotals:
        """Compute portfolio-level aggregate totals from holdings.

        Args:
            holdings: List of Holding models with amount and invested.

        Returns:
            PortfolioTotals with aggregated values.

        Raises:
            OperationError: If no holdings are provided.
        """
        logger.debug("Computing portfolio totals for %d holdings", len(holdings))
        if not holdings:
            raise OperationError("No holdings available for portfolio totals")

        quantize_amt = Decimal("0.01")

        total_current_value = sum((h.amount for h in holdings), Decimal(0)).quantize(
            quantize_amt
        )

        known_invested = [h.invested for h in holdings if h.invested is not None]
        total_invested: Decimal | None = (
            sum(known_invested, Decimal(0)).quantize(quantize_amt)
            if known_invested
            else None
        )

        # Compute gains only from holdings with known cost basis
        known_holdings = [h for h in holdings if h.invested is not None]
        total_gains: Decimal | None = None
        if total_invested is not None:
            known_current = sum(
                (h.amount for h in known_holdings), Decimal(0)
            ).quantize(quantize_amt)
            total_gains = (known_current - total_invested).quantize(quantize_amt)

        gains_percentage: Decimal | None = (
            (total_gains / total_invested).quantize(Decimal("0.0001"))
            if total_gains is not None
            and total_invested is not None
            and total_invested > 0
            else None
        )

        last_update: datetime.date = max(h.date for h in holdings)

        totals = PortfolioTotals(
            total_current_value=total_current_value,
            total_invested=total_invested,
            total_gains=total_gains,
            gains_percentage=gains_percentage,
            last_updated=last_update,
        )
        logger.debug(
            "Portfolio totals: invested=%s, current=%s",
            totals.total_invested,
            totals.total_current_value,
        )
        return totals

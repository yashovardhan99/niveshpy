"""Service for report generation and exporting."""

import datetime
import decimal
import heapq
from collections import defaultdict
from typing import Literal

from sqlalchemy import CTE, ColumnElement
from sqlalchemy.orm import aliased
from sqlmodel import col, func, literal, select
from sqlmodel.sql.expression import SelectOfScalar

from niveshpy.core.logging import logger
from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_filters_from_queries
from niveshpy.database import get_session
from niveshpy.exceptions import InvalidInputError, OperationError
from niveshpy.models.account import Account
from niveshpy.models.price import Price
from niveshpy.models.report import (
    HOLDING_COLUMN_MAPPINGS_PRICE,
    HOLDING_COLUMN_MAPPINGS_TXN,
    Allocation,
    Holding,
    PerformanceHolding,
    PerformanceResult,
    PortfolioTotals,
    SummaryResult,
)
from niveshpy.models.security import Security
from niveshpy.models.transaction import Transaction
from niveshpy.services.helpers import compute_invested_amount, compute_xirr


def get_holdings(queries: tuple[str, ...], limit: int, offset: int) -> list[Holding]:
    """Generate holdings report based on provided queries.

    Args:
        queries: Tuple of query strings to filter holdings.
        limit: Maximum number of results to return.
        offset: Number of results to skip from the start.

    Returns:
        List of Holding models matching the queries.
    """
    logger.info("Computing holdings for %d query filter(s)", len(queries))
    # Validate inputs
    if limit < 1:
        raise InvalidInputError(limit, "Limit must be positive.")
    if offset < 0:
        raise InvalidInputError(offset, "Offset cannot be negative.")

    where_clauses: list[ColumnElement[bool]] = get_filters_from_queries(
        queries, ast.Field.SECURITY, HOLDING_COLUMN_MAPPINGS_TXN
    )
    price_where_clauses: list[ColumnElement[bool]] = get_filters_from_queries(
        queries,
        ast.Field.SECURITY,
        HOLDING_COLUMN_MAPPINGS_PRICE,
        include_fields={ast.Field.SECURITY, ast.Field.DATE},
    )

    with get_session() as session:
        # First, get the total units held per security per account
        holding_units: CTE = (
            select(
                col(Transaction.account_id),
                col(Transaction.security_key),
                func.max(Transaction.transaction_date).label("last_transaction_date"),
                func.sum(Transaction.units).label("total_units"),
            )
            .join(Security, col(Security.key) == col(Transaction.security_key))
            .join(Account, col(Account.id) == col(Transaction.account_id))
            .where(*where_clauses)
            .group_by(col(Transaction.account_id), col(Transaction.security_key))
            .having(func.sum(Transaction.units) >= decimal.Decimal("0.001"))
            .cte("holding_units")
        )

        # Next, get the latest price for each security
        cte_prices: CTE = (
            select(
                Price,
                func.row_number()
                .over(partition_by=Price.security_key, order_by=col(Price.date).desc())
                .label("row_num"),
            )
            .join(Security, col(Security.key) == col(Price.security_key))
            .where(*price_where_clauses)
            .cte("cte_prices")
        )
        aliased_price: type[Price] = aliased(Price, cte_prices)
        latest_prices: CTE = (
            select(aliased_price)
            .where(cte_prices.c.row_num == 1)
            .order_by(col(aliased_price.security_key))
            .cte("latest_prices")
        )
        # Finally, join holdings with latest prices to get the desired output
        stm: SelectOfScalar[tuple] = (
            select(
                Security,
                Account,
                holding_units.c.total_units,
                (holding_units.c.total_units * latest_prices.c.close).label(
                    "holding_value"
                ),
                func.max(holding_units.c.last_transaction_date, latest_prices.c.date),
            )  # type: ignore[call-overload]
            .join(holding_units, col(Security.key) == holding_units.c.security_key)
            .join(Account, col(Account.id) == holding_units.c.account_id)
            .join(latest_prices, col(Security.key) == latest_prices.c.security_key)
            .order_by(Account.id, Security.key)
        )
        holding_rows = list(session.exec(stm.offset(offset).limit(limit)))

        # Compute invested amounts using FIFO on all transactions for held positions
        # Use only security/account filters (not date) since FIFO needs full history
        invested_amounts: dict[tuple[str, int], decimal.Decimal] = {}
        if holding_rows:
            cost_where_clauses: list[ColumnElement[bool]] = get_filters_from_queries(
                queries,
                ast.Field.SECURITY,
                HOLDING_COLUMN_MAPPINGS_TXN,
                include_fields={ast.Field.SECURITY, ast.Field.ACCOUNT},
            )
            cost_transactions = session.exec(
                select(Transaction)
                .join(Security)
                .join(Account)
                .where(*cost_where_clauses)
                .order_by(
                    col(Transaction.transaction_date).asc(),
                    col(Transaction.id).asc(),
                )
            ).all()
            invested_amounts = compute_invested_amount(cost_transactions)

        holdings = []
        for security, account, total_units, holding_value, as_of_date in holding_rows:
            key = (security.key, account.id)
            invested = invested_amounts.get(key)
            current_value = holding_value.quantize(decimal.Decimal("0.01"))
            holdings.append(
                Holding(
                    account=account,
                    security=security,
                    date=as_of_date,
                    units=total_units.quantize(decimal.Decimal("0.001")),
                    amount=current_value,
                    invested=invested,
                )
            )

    logger.info("Found %d holdings", len(holdings))
    return holdings


def get_performance(
    queries: tuple[str, ...],
    limit: int = 10000,
    offset: int = 0,
) -> PerformanceResult:
    """Generate portfolio performance report with per-holding XIRR.

    Returns a PerformanceResult containing per-holding performance data
    (each holding with gains and XIRR), portfolio-level totals, and
    the overall portfolio XIRR.

    Args:
        queries: Tuple of query strings to filter securities and accounts.
        limit: Maximum number of holdings to return.
        offset: Number of holdings to skip.

    Returns:
        PerformanceResult with holdings, totals, and portfolio_xirr.
    """
    logger.info("Computing performance metrics")
    # Fetch all holdings for portfolio-level metrics, then apply limit/offset for display
    all_holdings = get_holdings(queries, limit=10000, offset=0)
    if len(all_holdings) == 0:
        return PerformanceResult(
            holdings=[],
            totals=PortfolioTotals(
                total_current_value=decimal.Decimal("0"),
                total_invested=decimal.Decimal("0"),
                total_gains=decimal.Decimal("0"),
                gains_percentage=None,
            ),
        )
    totals = compute_portfolio_totals(all_holdings)

    # Apply limit/offset for per-holding display
    display_holdings = all_holdings[offset : offset + limit]

    cost_where_clauses: list[ColumnElement[bool]] = get_filters_from_queries(
        queries,
        ast.Field.SECURITY,
        HOLDING_COLUMN_MAPPINGS_TXN,
        include_fields={ast.Field.SECURITY, ast.Field.ACCOUNT},
    )
    with get_session() as session:
        transactions = session.exec(
            select(Transaction)
            .join(Security)
            .join(Account)
            .where(*cost_where_clauses)
            .order_by(
                col(Transaction.transaction_date).asc(),
                col(Transaction.id).asc(),
            )
        ).all()

    # Group transactions by (account_id, security_key) for per-holding XIRR
    txn_groups: dict[tuple[int, str], list[Transaction]] = defaultdict(list)
    for txn in transactions:
        txn_groups[(txn.account_id, txn.security_key)].append(txn)

    # Compute per-holding XIRR and build PerformanceHolding models
    holdings: list[PerformanceHolding] = []
    for h in display_holdings:
        key = (h.account.id, h.security.key) if h.account.id is not None else None
        holding_xirr: decimal.Decimal | None = None
        if key and key in txn_groups:
            try:
                holding_xirr = compute_xirr(txn_groups[key], h.amount)
            except OperationError:
                holding_xirr = None
        holdings.append(PerformanceHolding.from_holding(h, holding_xirr))

    # Compute portfolio-wide XIRR
    logger.debug("Computing XIRR with %d cash flows", len(transactions))
    try:
        totals.xirr = compute_xirr(list(transactions), totals.total_current_value)
    except OperationError:
        pass

    logger.info("Performance computed: %d holdings", len(holdings))
    return PerformanceResult(
        holdings=holdings,
        totals=totals,
    )


def get_allocation(
    queries: tuple[str, ...], group_by: Literal["both", "type", "category"]
) -> list[Allocation]:
    """Generate allocation report based on provided queries.

    Args:
        queries: Tuple of query strings to filter holdings.
        group_by: Grouping method for allocation report.

    Returns:
        List of Allocation models matching the queries.
    """
    logger.info("Computing allocation grouped by %s", group_by)
    where_clauses: list[ColumnElement[bool]] = get_filters_from_queries(
        queries, ast.Field.SECURITY, HOLDING_COLUMN_MAPPINGS_TXN
    )
    price_where_clauses: list[ColumnElement[bool]] = get_filters_from_queries(
        queries,
        ast.Field.SECURITY,
        HOLDING_COLUMN_MAPPINGS_PRICE,
        include_fields={ast.Field.SECURITY, ast.Field.DATE},
    )

    with get_session() as session:
        # First, get the total units held per security
        holding_units: CTE = (
            select(
                col(Transaction.security_key),
                func.max(Transaction.transaction_date).label("last_transaction_date"),
                func.sum(Transaction.units).label("total_units"),
            )
            .join(Security, col(Security.key) == col(Transaction.security_key))
            .join(Account, col(Account.id) == col(Transaction.account_id))
            .where(*where_clauses)
            .group_by(col(Transaction.security_key))
            .having(func.sum(Transaction.units) >= decimal.Decimal("0.001"))
            .cte("holding_units")
        )

        # Next, get the latest price for each security
        cte_prices: CTE = (
            select(
                Price,
                func.row_number()
                .over(partition_by=Price.security_key, order_by=col(Price.date).desc())
                .label("row_num"),
            )
            .join(Security, col(Security.key) == col(Price.security_key))
            .where(*price_where_clauses)
            .cte("cte_prices")
        )
        aliased_price: type[Price] = aliased(Price, cte_prices)
        latest_prices: CTE = (
            select(aliased_price)
            .where(cte_prices.c.row_num == 1)
            .order_by(col(aliased_price.security_key))
            .cte("latest_prices")
        )
        # Finally, join holdings with latest prices to get the desired output
        cte_holdings: CTE = (
            select(
                col(Security.category) if group_by in ("both", "category") else None,
                col(Security.type) if group_by in ("both", "type") else None,
                (holding_units.c.total_units * latest_prices.c.close).label(
                    "holding_value"
                ),
                func.max(
                    holding_units.c.last_transaction_date, latest_prices.c.date
                ).label("date"),
            )
            .join(holding_units, col(Security.key) == holding_units.c.security_key)
            .join(latest_prices, col(Security.key) == latest_prices.c.security_key)
            .cte("cte_holdings")
        )
        cte_total: CTE = select(
            func.sum(cte_holdings.c.holding_value).label("total_value")
        ).cte("cte_total")
        stm: SelectOfScalar[tuple] = (
            select(
                col(cte_holdings.c.category)
                if group_by in ("both", "category")
                else None,
                col(cte_holdings.c.type) if group_by in ("both", "type") else None,
                func.min(cte_holdings.c.date).label("date"),
                func.sum(cte_holdings.c.holding_value).label("total_amount"),
                (
                    func.sum(cte_holdings.c.holding_value) / cte_total.c.total_value
                ).label("proportion"),
            )  # type: ignore[call-overload]
            .join(cte_total, literal(True))
            .group_by(
                col(cte_holdings.c.category)
                if group_by in ("both", "category")
                else None,
                col(cte_holdings.c.type) if group_by in ("both", "type") else None,
            )
            .order_by(func.sum(cte_holdings.c.holding_value).desc())
        )
        result = session.exec(stm)
        return [
            Allocation(
                security_category=row[0],
                security_type=row[1],
                date=row[2],
                amount=row[3].quantize(decimal.Decimal("0.01")),
                allocation=row[4].quantize(decimal.Decimal("0.0001")),
            )
            for row in result
        ]


def compute_portfolio_totals(holdings: list[Holding]) -> PortfolioTotals:
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

    quantize_amt = decimal.Decimal("0.01")

    total_current_value = sum(
        (h.amount for h in holdings), decimal.Decimal(0)
    ).quantize(quantize_amt)

    known_invested = [h.invested for h in holdings if h.invested is not None]
    total_invested: decimal.Decimal | None = (
        sum(known_invested, decimal.Decimal(0)).quantize(quantize_amt)
        if known_invested
        else None
    )

    # Compute gains only from holdings with known cost basis
    known_holdings = [h for h in holdings if h.invested is not None]
    total_gains: decimal.Decimal | None = None
    if total_invested is not None:
        known_current = sum(
            (h.amount for h in known_holdings), decimal.Decimal(0)
        ).quantize(quantize_amt)
        total_gains = (known_current - total_invested).quantize(quantize_amt)

    gains_percentage: decimal.Decimal | None = (
        (total_gains / total_invested).quantize(decimal.Decimal("0.0001"))
        if total_gains is not None and total_invested is not None and total_invested > 0
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


def get_summary(
    queries: tuple[str, ...],
    top_n: int = 5,
) -> SummaryResult:
    """Generate portfolio summary combining metrics, top holdings, and allocation."""
    logger.info("Generating portfolio summary (top_n=%d)", top_n)
    # Get all holdings and compute totals for summary metrics
    result = get_performance(queries)

    # Get top N holdings by current value for summary display
    top_holdings = heapq.nlargest(top_n, result.holdings, key=lambda h: h.current_value)

    # Get allocation by category for summary display (could also do by type or both if desired)
    allocation = get_allocation(queries, group_by="category")

    return SummaryResult(
        as_of=result.holdings[0].date if result.holdings else None,
        metrics=result.totals,  # PortfolioTotals already has everything
        top_holdings=top_holdings,
        allocation=allocation,
    )

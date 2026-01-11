"""Service for report generation and exporting."""

import decimal
from collections.abc import Sequence
from typing import Literal

from sqlalchemy import CTE, ColumnElement
from sqlalchemy.orm import aliased
from sqlmodel import col, func, literal, select
from sqlmodel.sql.expression import SelectOfScalar

from niveshpy.core.query import ast
from niveshpy.core.query.prepare import get_filters_from_queries
from niveshpy.database import get_session
from niveshpy.exceptions import InvalidInputError
from niveshpy.models.account import Account
from niveshpy.models.price import Price
from niveshpy.models.report import (
    HOLDING_COLUMN_MAPPINGS_PRICE,
    HOLDING_COLUMN_MAPPINGS_TXN,
    Allocation,
    AllocationByCategory,
    AllocationByType,
    Holding,
)
from niveshpy.models.security import Security
from niveshpy.models.transaction import Transaction


def get_holdings(queries: tuple[str, ...], limit: int, offset: int) -> list[Holding]:
    """Generate holdings report based on provided queries.

    Args:
        queries: Tuple of query strings to filter holdings.
        limit: Maximum number of results to return.
        offset: Number of results to skip from the start.

    Returns:
        List of Holding models matching the queries.
    """
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
        holdings = [
            Holding(
                account=account,
                security=security,
                date=as_of_date,
                units=total_units.quantize(decimal.Decimal("0.001")),
                amount=holding_value.quantize(decimal.Decimal("0.01")),
            )
            for security, account, total_units, holding_value, as_of_date in session.exec(
                stm.offset(offset).limit(limit)
            )
        ]

    return holdings


def get_allocation(
    queries: tuple[str, ...], group_by: Literal["both", "type", "category"]
) -> Sequence[Allocation | AllocationByCategory | AllocationByType]:
    """Generate allocation report based on provided queries.

    Args:
        queries: Tuple of query strings to filter holdings.
        group_by: Grouping method for allocation report.

    Returns:
        Sequence of Allocation models matching the queries.
    """
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
        allocations: list[Allocation | AllocationByCategory | AllocationByType] = []
        for row in result:
            if group_by == "both":
                allocations.append(
                    Allocation(
                        security_category=row[0],
                        security_type=row[1],
                        date=row[2],
                        amount=row[3].quantize(decimal.Decimal("0.01")),
                        allocation=row[4].quantize(decimal.Decimal("0.0001")),
                    )
                )
            elif group_by == "category":
                allocations.append(
                    AllocationByCategory(
                        security_category=row[0],
                        date=row[2],
                        amount=row[3].quantize(decimal.Decimal("0.01")),
                        allocation=row[4].quantize(decimal.Decimal("0.0001")),
                    )
                )
            else:  # group_by == "type"
                allocations.append(
                    AllocationByType(
                        security_type=row[1],
                        date=row[2],
                        amount=row[3].quantize(decimal.Decimal("0.01")),
                        allocation=row[4].quantize(decimal.Decimal("0.0001")),
                    )
                )
        return allocations

"""Service for report generation and exporting."""

import decimal

from sqlalchemy import CTE, ColumnElement
from sqlalchemy.orm import aliased
from sqlmodel import col, func, select
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
            )  # type: ignore[no-matching-overload, call-overload]
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

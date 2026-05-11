"""Query Builder for SQLite."""

from __future__ import annotations

import functools
from collections.abc import Iterable, Sequence
from enum import Enum
from textwrap import dedent
from typing import Any, Literal, Self

from attrs import define, field, frozen

from niveshpy.infrastructure.sqlite.converters import get_converter


class Expr(str):
    """NewType for SQL expressions to distinguish them from regular strings."""

    def alias(self, alias: str | None) -> AliasedExpr:
        """Create an aliased expression for this SQL expression."""
        return AliasedExpr(self, alias)


@frozen
class Condition:
    """Class to represent a SQL condition with its expression and parameters.

    This class should not be created directly outside of the query builder.
    Instead, use helper functions like `Col().eq()`, `Fn()`, `in_()`, etc. to create conditions.
    """

    expression: Expr
    params: tuple[Any, ...] = ()


def q(column_or_table: str) -> str:
    """Quote an identifier (column or table name) for use in SQL queries."""
    if column_or_table.startswith('"') and column_or_table.endswith('"'):
        return column_or_table  # Already quoted
    if "." in column_or_table:
        parts = column_or_table.split(".")
        return ".".join(f'"{part}"' for part in parts)
    return f'"{column_or_table}"'


@frozen
class SqlExpr:
    """A SQL expression that can participate in conditions and comparisons.

    This is the base expression type used by both `Col()` and `Fn()`.
    Supports comparison operators, NULL checks, BETWEEN, and IN conditions.
    """

    _sql: str
    _params: tuple[Any, ...]

    def __str__(self) -> str:
        """Render the SQL expression as a string, with parameters represented as placeholders."""
        return self._sql

    def _create_simple_condition(self, operator: str, value: Any) -> Condition:
        """Create a simple binary condition expression."""
        if isinstance(value, SqlExpr):
            return Condition(
                Expr(f"{self} {operator} {value}"),
                (*self._params, *value._params),
            )
        return Condition(Expr(f"{self} {operator} ?"), (*self._params, value))

    eq = functools.partialmethod(_create_simple_condition, "=")
    """Create an equality condition."""
    ne = functools.partialmethod(_create_simple_condition, "!=")
    """Create a not-equal condition."""
    gt = functools.partialmethod(_create_simple_condition, ">")
    """Create a greater-than condition."""
    ge = functools.partialmethod(_create_simple_condition, ">=")
    """Create a greater-than-or-equal condition."""
    lt = functools.partialmethod(_create_simple_condition, "<")
    """Create a less-than condition."""
    le = functools.partialmethod(_create_simple_condition, "<=")
    """Create a less-than-or-equal condition."""

    def is_null(self) -> Condition:
        """Create an IS NULL condition."""
        return Condition(Expr(f"{self} IS NULL"), self._params)

    def is_not_null(self) -> Condition:
        """Create an IS NOT NULL condition."""
        return Condition(Expr(f"{self} IS NOT NULL"), self._params)

    def between(self, low: Any, high: Any) -> Condition:
        """Create a BETWEEN condition."""
        left_sql, left_params = (
            (str(low), (*self._params, *low._params))
            if isinstance(low, SqlExpr)
            else ("?", (*self._params, low))
        )
        right_sql, right_params = (
            (str(high), (*left_params, *high._params))
            if isinstance(high, SqlExpr)
            else ("?", (*left_params, high))
        )
        return Condition(
            Expr(f"{self} BETWEEN {left_sql} AND {right_sql}"), right_params
        )

    def not_between(self, low: Any, high: Any) -> Condition:
        """Create a NOT BETWEEN condition."""
        left_sql, left_params = (
            (str(low), (*self._params, *low._params))
            if isinstance(low, SqlExpr)
            else ("?", (*self._params, low))
        )
        right_sql, right_params = (
            (str(high), (*left_params, *high._params))
            if isinstance(high, SqlExpr)
            else ("?", (*left_params, high))
        )
        return Condition(
            Expr(f"{self} NOT BETWEEN {left_sql} AND {right_sql}"), right_params
        )

    def in_(self, values: Sequence[Any]) -> Condition:
        """Create an IN condition."""
        return in_(str(self), *values)

    def not_in(self, values: Sequence[Any]) -> Condition:
        """Create a NOT IN condition."""
        return not_in(str(self), *values)

    def to_condition(self) -> Condition:
        """Convert this expression to a Condition (for boolean function expressions)."""
        return Condition(Expr(str(self)), self._params)

    # OPERATOR OVERLOADS

    def __mul__(self, other: Any) -> SqlExpr:
        """Support multiplication operator for expressions, useful for things like calculating total value."""
        if isinstance(other, SqlExpr):
            return SqlExpr(f"{self} * {other}", (*self._params, *other._params))
        return SqlExpr(f"{self} * ?", (*self._params, other))

    def __truediv__(self, other: Any) -> SqlExpr:
        """Support division operator for expressions, useful for things like calculating allocation."""
        if isinstance(other, SqlExpr):
            return SqlExpr(f"{self} / {other}", (*self._params, *other._params))
        return SqlExpr(f"{self} / ?", (*self._params, other))

    def alias(self, alias: str | None) -> AliasedExpr:
        """Create an aliased expression for this SQL expression."""
        if self._params:
            raise ValueError(
                "Cannot alias an expression with parameters. Use an aliased column or function instead."
            )
        return Expr(self._sql).alias(alias)


@frozen(init=False)
class Col(SqlExpr):
    """A column reference expression that can be used in conditions and comparisons.

    Attributes:
        name: The column name, which can include a table prefix (e.g., "table.column").
        table: Optional table name for disambiguation. If the name includes a dot, it will be split into table and column parts.
    """

    name: str
    table: str | None = None

    def __init__(self, table_or_name: str, name: str | None = None) -> None:
        """Create a column reference expression.

        Args:
            table_or_name: Table name or column name (if name is None).
            name: Optional column name if table_or_name is a table name.

        If table_or_name contains a dot, it will be split into table and column parts.
        """
        if "." in table_or_name and name is None:
            # Split into table and column if not explicitly provided
            table, name = table_or_name.split(".", 1)
        elif name is None:
            # No dot and no explicit name means table_or_name is the column
            name = table_or_name
            table = None
        else:
            # Explicit table and name provided
            table = table_or_name

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "table", table)
        object.__setattr__(self, "_params", ())
        object.__setattr__(self, "_sql", self._get_sql())
        super().__init__(self._sql, self._params)

    def _get_sql(self) -> str:
        if self.name == "*":
            if self.table:
                _sql = f"{q(self.table)}.*"
            else:
                _sql = "*"
        elif self.table:
            _sql = f"{q(self.table)}.{q(self.name)}"
        else:
            _sql = q(self.name)
        return _sql


def in_(column: str | tuple[str, ...], *values: Any, not_: bool = False) -> Condition:
    """Create an IN condition with the given values."""
    if isinstance(column, tuple):
        if values and not isinstance(values[0], tuple):
            raise TypeError(
                "For multi-column IN conditions, values must be tuples matching the number of columns."
            )
        cols = len(column)
        placeholders = ", ".join([f"({', '.join(['?'] * cols)})"] * len(values))
        return Condition(
            Expr(
                f"({', '.join(column)}) {'NOT IN' if not_ else 'IN'} ({placeholders})"
            ),
            tuple(p for v in values for p in v),
        )
    else:
        if values and isinstance(values[0], tuple):
            raise TypeError(
                "For single column IN conditions, values should not be tuples."
            )
        placeholders = ", ".join(["?"] * len(values))
        return Condition(
            Expr(f"{column} {'NOT IN' if not_ else 'IN'} ({placeholders})"), values
        )


not_in = functools.partial(in_, not_=True)


def Fn(function_name: str, *args: SqlExpr | Any) -> SqlExpr:
    """Create a SQL function expression.

    Args:
        function_name: The SQL function name (e.g., "SUM", "COUNT", "IREGEXP").
        args: Arguments to the function. SqlExpr args are rendered as-is,
              other values become bind parameters (?).

    Returns:
        A SqlExpr that can be used in comparisons or directly as a boolean condition.
    """
    fn_args = []
    params: list[Any] = []
    for arg in args:
        if isinstance(arg, SqlExpr):
            fn_args.append(str(arg))
            params.extend(arg._params)
        else:
            fn_args.append("?")
            params.append(arg)
    return SqlExpr(f"{function_name}({', '.join(fn_args)})", tuple(params))


def or_(*conditions: Condition) -> Condition:
    """Combine conditions with OR, wrapped in parentheses."""
    expression = Expr("(" + " OR ".join(str(c.expression) for c in conditions) + ")")
    params = tuple(p for c in conditions for p in c.params)
    return Condition(expression, params)


@frozen
class AliasedExpr:
    """A SQL expression with an optional alias for use in SELECT clauses."""

    expression: Expr
    alias: str | None = None

    def __str__(self) -> str:
        """Render the aliased expression as a string, including the alias if present."""
        if self.alias:
            return f"{self.expression} AS {self.alias}"
        return str(self.expression)


class _JoinType(Enum):
    INNER = "JOIN"
    LEFT = "LEFT JOIN"
    OUTER = "OUTER JOIN"
    CROSS = "CROSS JOIN"


@frozen
class _Join:
    type: _JoinType
    table: AliasedExpr
    on: Sequence[Condition]


@frozen
class _CTE:
    name: str
    query: Query

    def _build_sql(self) -> Iterable[str]:
        yield f"{self.name} AS (\n"
        yield from self.query._build_sql(indent="  ")
        yield ")"

    def __str__(self) -> str:
        return "".join(self._build_sql())


@define
class Query:
    """Query Builder for SQLite."""

    class _SelectFlag(Enum):
        DEFAULT = ""
        DISTINCT = "DISTINCT"
        ALL = "ALL"

    cte_expressions: list[_CTE] = field(factory=list)
    select_flag: _SelectFlag = _SelectFlag.DEFAULT
    select_expressions: list[AliasedExpr] = field(factory=list)
    from_expressions: list[AliasedExpr] = field(factory=list)
    join_expressions: list[_Join] = field(factory=list)
    where_expressions: list[Condition] = field(factory=list)
    group_by_expressions: list[Expr] = field(factory=list)
    having_expressions: list[Condition] = field(factory=list)
    order_by_expressions: list[Expr] = field(factory=list)
    limit_expression: int | None = None
    offset_expression: int | None = None

    def with_cte(self, name: str, query: Query) -> Self:
        """Add a Common Table Expression (CTE) to the query."""
        self.cte_expressions.append(_CTE(name, query))
        return self

    def select(
        self,
        *columns: str | tuple[str, str] | Col | AliasedExpr,
        distinct: bool = False,
        all: bool = False,
        prefix_table: str | None = None,
    ) -> Self:
        """Build a SELECT query.

        Args:
            columns: Columns to select, specified as strings, (expression, alias) tuples, or _AliasedExpr instances.
            distinct: If True, add DISTINCT to the SELECT clause.
            all: If True, add ALL to the SELECT clause.
            prefix_table: Optional table name to prefix column names with for disambiguation.
                This will only apply to columns specified as strings or (expression, alias) tuples.

        Returns:
            Self: The Query object with the SELECT clause added.

        Raises:
            ValueError: If both distinct and all are True, which is not allowed in SQL.
        """
        if distinct and all:
            raise ValueError("Cannot use both DISTINCT and ALL in a SELECT query.")
        if distinct:
            self.select_flag = self._SelectFlag.DISTINCT
        if all:
            self.select_flag = self._SelectFlag.ALL

        if prefix_table:
            prefix_table = q(prefix_table)

        parsed_columns: list[AliasedExpr] = []
        for column in columns:
            name: str
            alias: str | None = None
            if isinstance(column, AliasedExpr):
                parsed_columns.append(column)
                continue
            elif isinstance(column, Col):
                parsed_columns.append(column.alias(None))
                continue
            elif isinstance(column, tuple):
                name, alias = column
            else:
                name = column

            if prefix_table:
                name = f"{prefix_table}.{name}"

            parsed_columns.append(Expr(name).alias(alias))

        self.select_expressions.extend(parsed_columns)
        return self

    def from_(self, *tables: str | tuple[str, str]) -> Self:
        """Add FROM clause to the query."""
        for table in tables:
            if isinstance(table, tuple):
                name, alias = table
                self.from_expressions.append(Expr(q(name)).alias(alias))
            else:
                self.from_expressions.append(Expr(q(table)).alias(None))
        return self

    def join(
        self,
        table: str | tuple[str, str],
        *on_: Condition,
        type: Literal["inner", "left", "outer", "cross"] = "inner",
    ) -> Self:
        """Add JOIN clause to the query."""
        if isinstance(table, tuple):
            name, alias = table
            table_expr = AliasedExpr(Expr(q(name)), alias)
        else:
            table_expr = AliasedExpr(Expr(q(table)))
        self.join_expressions.append(_Join(_JoinType[type.upper()], table_expr, on_))
        return self

    def where(self, *conditions: Condition) -> Self:
        """Add WHERE clause to the query."""
        self.where_expressions.extend(conditions)
        return self

    def group_by(self, *columns: str | Col) -> Self:
        """Add GROUP BY clause to the query."""
        self.group_by_expressions.extend(Expr(str(column)) for column in columns)
        return self

    def having(self, *conditions: Condition) -> Self:
        """Add HAVING clause to the query."""
        self.having_expressions.extend(conditions)
        return self

    def order_by(self, *columns: str) -> Self:
        """Add ORDER BY clause to the query."""
        self.order_by_expressions.extend(Expr(column) for column in columns)
        return self

    def limit(self, limit: int) -> Self:
        """Add LIMIT clause to the query."""
        self.limit_expression = limit
        return self

    def offset(self, offset: int) -> Self:
        """Add OFFSET clause to the query."""
        self.offset_expression = offset
        return self

    def __str__(self) -> str:
        """Generate the SQL query string."""
        return "".join(self._build_sql())

    @property
    def params(self) -> tuple[Any, ...]:
        """Build the list of parameters for the query."""
        params = []
        converter = get_converter()
        for cte in self.cte_expressions:
            params.extend(cte.query.params)
        for join in self.join_expressions:
            for cond in join.on:
                params.extend(cond.params)
        for condition in self.where_expressions + self.having_expressions:
            params.extend(condition.params)
        if self.limit_expression is not None:
            params.append(self.limit_expression)
        if self.offset_expression is not None:
            params.append(self.offset_expression)
        return tuple(converter.unstructure(params))

    def _build_sql(self, indent="") -> Iterable[str]:
        if self.cte_expressions:
            yield "WITH "
            for i, cte in enumerate(self.cte_expressions):
                yield from cte._build_sql()
                if i < len(self.cte_expressions) - 1:
                    yield ",\n"
            yield "\n"
        if self.select_expressions:
            yield f"{indent}SELECT"
            if self.select_flag.value:
                yield f" {self.select_flag.value}"
            yield "\n"
            yield from self._build_expressions(
                self.select_expressions, indent=indent + "  "
            )
        if self.from_expressions:
            yield f"{indent}FROM\n"
            yield from self._build_expressions(
                self.from_expressions, indent=indent + "  "
            )
        if self.join_expressions:
            for join in self.join_expressions:
                yield f"{indent}{join.type.value} {join.table}\n"
                if join.on:
                    yield f"{indent}ON\n"
                    yield from self._build_expressions(
                        join.on, sep=" AND ", indent=indent + "  "
                    )
        if self.where_expressions:
            yield f"{indent}WHERE\n"
            yield from self._build_expressions(
                self.where_expressions, sep=" AND ", indent=indent + "  "
            )
        if self.group_by_expressions:
            yield f"{indent}GROUP BY\n"
            yield from self._build_expressions(
                self.group_by_expressions, indent=indent + "  "
            )
        if self.having_expressions:
            yield f"{indent}HAVING\n"
            yield from self._build_expressions(
                self.having_expressions, sep=" AND ", indent=indent + "  "
            )
        if self.order_by_expressions:
            yield f"{indent}ORDER BY\n"
            yield from self._build_expressions(
                self.order_by_expressions, indent=indent + "  "
            )
        if self.limit_expression is not None:
            yield f"{indent}LIMIT ?\n"
        if self.offset_expression is not None:
            yield f"{indent}OFFSET ?\n"

    def _build_expressions(
        self,
        expressions: Sequence[AliasedExpr]
        | Sequence[str]
        | Sequence[Expr]
        | Sequence[Condition],
        sep: str = ",",
        indent: str = "  ",
    ) -> Iterable[str]:
        for i, expr in enumerate(expressions):
            yield indent
            if i > 0 and sep != ",":
                yield sep.lstrip()
            if isinstance(expr, Condition):
                yield str(expr.expression)
            else:
                yield str(expr)
            if i < len(expressions) - 1 and sep == ",":
                yield sep
            yield "\n"


class _InsertFlag(Enum):
    DEFAULT = ""
    OR_REPLACE = "OR REPLACE"
    OR_IGNORE = "OR IGNORE"


@define
class Insert:
    """Insert Builder for SQLite."""

    table: str = ""
    flag: _InsertFlag = _InsertFlag.DEFAULT
    columns: list[str] = field(factory=list)
    values: list[tuple[Any, ...]] = field(factory=list)
    returning_columns: list[AliasedExpr] = field(factory=list)

    def or_ignore(self) -> Self:
        """Set the insert flag to OR IGNORE."""
        self.flag = _InsertFlag.OR_IGNORE
        return self

    def or_replace(self) -> Self:
        """Set the insert flag to OR REPLACE."""
        self.flag = _InsertFlag.OR_REPLACE
        return self

    def into(self, table: str) -> Self:
        """Specify the table to insert into."""
        self.table = q(table)
        return self

    def columns_(self, *columns: str) -> Self:
        """Specify the columns to insert values into."""
        self.columns.extend(q(column) for column in columns)
        return self

    def values_(self, *values: Any) -> Self:
        """Add a row of values to insert.

        This method can be called multiple times to add multiple rows.
        The number of values must match the number of columns (if specified).
        """
        if self.columns and len(values) != len(self.columns):
            raise ValueError(f"Expected {len(self.columns)} values, got {len(values)}.")
        self.values.append(tuple(values))
        return self

    def returning(self, *columns: AliasedExpr) -> Self:
        """Add a RETURNING clause to the insert statement."""
        self.returning_columns.extend(columns)
        return self

    def __str__(self) -> str:
        """Generate the SQL insert statement."""
        if not self.table:
            raise ValueError("Table must be specified.")

        sql = dedent(f"""\
        INSERT {self.flag.value}
        INTO {self.table}
        """)

        if self.columns:
            columns_str = ", ".join(self.columns)
            sql += f"({columns_str})\n"

            placeholders = ", ".join(["?"] * len(self.columns))
            sql += "VALUES\n"
            sql += f"({placeholders})\n"

        if self.returning_columns:
            returning_str = ", ".join(str(col) for col in self.returning_columns)
            sql += f"\nRETURNING {returning_str}"

        return sql

    @property
    def params(self) -> tuple[Any, ...]:
        """Get the parameters for the insert statement."""
        converter = get_converter()
        return tuple(
            converter.unstructure(value) for row in self.values for value in row
        )


@define
class Delete:
    """Delete Builder for SQLite."""

    table: str = ""
    where_expressions: list[Condition] = field(factory=list)
    returning_columns: list[AliasedExpr] = field(factory=list)

    def from_(self, table: str) -> Self:
        """Specify the table to delete from."""
        self.table = q(table)
        return self

    def where(self, *conditions: Condition) -> Self:
        """Add WHERE clause to the delete statement."""
        self.where_expressions.extend(conditions)
        return self

    def returning(self, *columns: AliasedExpr) -> Self:
        """Add a RETURNING clause to the delete statement."""
        self.returning_columns.extend(columns)
        return self

    def __str__(self) -> str:
        """Generate the SQL delete statement."""
        if not self.table:
            raise ValueError("Table must be specified.")

        sql = "DELETE FROM " + self.table + "\n"  # noqa: S608

        if self.where_expressions:
            sql += "WHERE "
            sql += " AND ".join(str(cond.expression) for cond in self.where_expressions)

        if self.returning_columns:
            returning_str = ", ".join(str(col) for col in self.returning_columns)
            sql += f"\nRETURNING {returning_str}"

        return sql

    @property
    def params(self) -> tuple[Any, ...]:
        """Get the parameters for the delete statement."""
        converter = get_converter()
        params = []
        for condition in self.where_expressions:
            params.extend(converter.unstructure(value) for value in condition.params)
        return tuple(params)


# Select helper constants for mapping fields to columns in repositories

ACCOUNT_COLUMNS = ("id", "name", "institution", ("created_at", "created"), "properties")
"""Mapping of AccountPublic attributes to database column names for accounts."""

SECURITY_COLUMNS = ("key", "name", "type", "category", "properties", "created")
"""Mapping of SecurityPublic attributes to database column names for securities."""

PRICE_COLUMNS = (
    "security_key",
    "date",
    "open",
    "high",
    "low",
    "close",
    "properties",
    "created",
)
"""Mapping of PricePublic attributes to database column names for prices."""

PRICE_CREATE_COLUMNS = (
    "security_key",
    "date",
    "open",
    "high",
    "low",
    "close",
    "properties",
)
"""Mapping of PriceCreate attributes to database column names for price creation."""

TRANSACTION_COLUMNS = (
    "id",
    "transaction_date",
    "type",
    "description",
    "amount",
    "units",
    "security_key",
    "account_id",
    "properties",
    "created",
)
"""Mapping of TransactionPublic attributes to database column names for transactions."""

TRANSACTION_CREATE_COLUMNS = (
    "transaction_date",
    "type",
    "description",
    "amount",
    "units",
    "security_key",
    "account_id",
    "properties",
)
"""Mapping of TransactionCreate attributes to database column names for transaction creation."""

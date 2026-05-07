"""Query Builder for SQLite."""

from __future__ import annotations

import functools
from collections.abc import Iterable, Sequence
from enum import Enum
from textwrap import dedent
from typing import Any, Literal, NewType, Self, overload

from attrs import define, field, frozen

_Expr = NewType("_Expr", str)


@frozen
class _Condition:
    expression: _Expr
    params: tuple[Any, ...] = ()

    @classmethod
    def from_arg(cls, arg: str | tuple[str, Any] | tuple[str, Any, Any]) -> Self:
        if isinstance(arg, tuple):
            return cls(_Expr(arg[0]), tuple(arg[1:]))
        return cls(_Expr(arg))


ConditionType = str | tuple[str, Any] | tuple[str, Any, Any] | _Condition


@overload
def in_(column: str, *values: Any, not_: bool = False) -> _Condition: ...


@overload
def in_(
    column: tuple[str, ...], *values: tuple[Any, ...], not_: bool = False
) -> _Condition: ...


def in_(column: str | tuple[str, ...], *values: Any, not_: bool = False) -> _Condition:
    """Create an IN condition with the given values."""
    if isinstance(column, tuple):
        cols = len(column)
        placeholders = ", ".join([f"({', '.join(['?'] * cols)})"] * len(values))
        return _Condition(
            _Expr(
                f"({', '.join(column)}) {'NOT IN' if not_ else 'IN'} ({placeholders})"
            ),
            tuple(p for v in values for p in v),
        )
    else:
        placeholders = ", ".join(["?"] * len(values))
        return _Condition(
            _Expr(f"{column} {'NOT IN' if not_ else 'IN'} ({placeholders})"), values
        )


not_in = functools.partial(in_, not_=True)


def or_(*conditions: ConditionType) -> _Condition:
    """Combine conditions with OR, wrapped in parentheses."""
    parsed = [
        _Condition.from_arg(c) if not isinstance(c, _Condition) else c
        for c in conditions
    ]
    expression = _Expr("(" + " OR ".join(str(c.expression) for c in parsed) + ")")
    params = tuple(p for c in parsed for p in c.params)
    return _Condition(expression, params)


@frozen
class _AliasedExpr:
    expression: _Expr
    alias: str | None = None

    @classmethod
    def from_arg(cls, arg: str | tuple[str, str]) -> Self:
        if isinstance(arg, tuple):
            return cls(_Expr(arg[0]), arg[1])
        return cls(_Expr(arg))

    def __str__(self) -> str:
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
    table: _AliasedExpr
    on: Sequence[_Condition]


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
    select_expressions: list[_AliasedExpr] = field(factory=list)
    from_expressions: list[_AliasedExpr] = field(factory=list)
    join_expressions: list[_Join] = field(factory=list)
    where_expressions: list[_Condition] = field(factory=list)
    group_by_expressions: list[_Expr] = field(factory=list)
    having_expressions: list[_Condition] = field(factory=list)
    order_by_expressions: list[_Expr] = field(factory=list)
    limit_expression: int | None = None
    offset_expression: int | None = None

    def with_cte(self, name: str, query: Query) -> Self:
        """Add a Common Table Expression (CTE) to the query."""
        self.cte_expressions.append(_CTE(name, query))
        return self

    def select(
        self, *columns: str | tuple[str, str], distinct: bool = False, all: bool = False
    ) -> Self:
        """Build a SELECT query."""
        if distinct and all:
            raise ValueError("Cannot use both DISTINCT and ALL in a SELECT query.")
        if distinct:
            self.select_flag = self._SelectFlag.DISTINCT
        if all:
            self.select_flag = self._SelectFlag.ALL
        self.select_expressions.extend(
            _AliasedExpr.from_arg(column) for column in columns
        )
        return self

    def from_(self, *tables: str | tuple[str, str]) -> Self:
        """Add FROM clause to the query."""
        self.from_expressions.extend(_AliasedExpr.from_arg(table) for table in tables)
        return self

    def join(
        self,
        table: str | tuple[str, str],
        *on: ConditionType,
        type: Literal["inner", "left", "outer", "cross"] = "inner",
    ) -> Self:
        """Add JOIN clause to the query."""
        self.join_expressions.append(
            _Join(
                _JoinType[type.upper()],
                _AliasedExpr.from_arg(table),
                [
                    cond if isinstance(cond, _Condition) else _Condition.from_arg(cond)
                    for cond in on
                ],
            )
        )
        return self

    def where(self, *conditions: ConditionType) -> Self:
        """Add WHERE clause to the query."""
        for condition in conditions:
            if isinstance(condition, _Condition):
                self.where_expressions.append(condition)
            else:
                self.where_expressions.append(_Condition.from_arg(condition))
        return self

    def group_by(self, *columns: str) -> Self:
        """Add GROUP BY clause to the query."""
        self.group_by_expressions.extend(_Expr(column) for column in columns)
        return self

    def having(self, *conditions: ConditionType) -> Self:
        """Add HAVING clause to the query."""
        for condition in conditions:
            if isinstance(condition, _Condition):
                self.having_expressions.append(condition)
            else:
                self.having_expressions.append(_Condition.from_arg(condition))
        return self

    def order_by(self, *columns: str) -> Self:
        """Add ORDER BY clause to the query."""
        self.order_by_expressions.extend(_Expr(column) for column in columns)
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
        return tuple(params)

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
        expressions: Sequence[_AliasedExpr]
        | Sequence[str]
        | Sequence[_Expr]
        | Sequence[_Condition],
        sep: str = ",",
        indent: str = "  ",
    ) -> Iterable[str]:
        for i, expr in enumerate(expressions):
            yield indent
            if i > 0 and sep != ",":
                yield sep.lstrip()
            if isinstance(expr, _Condition):
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
    returning_columns: list[_AliasedExpr] = field(factory=list)

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
        self.table = table
        return self

    def columns_(self, *columns: str) -> Self:
        """Specify the columns to insert values into."""
        self.columns.extend(columns)
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

    def returning(self, *columns: str | tuple[str, str]) -> Self:
        """Add a RETURNING clause to the insert statement."""
        self.returning_columns.extend(
            _AliasedExpr.from_arg(column) for column in columns
        )
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
        return tuple(value for row in self.values for value in row)


@define
class Delete:
    """Delete Builder for SQLite."""

    table: str = ""
    where_expressions: list[_Condition] = field(factory=list)
    returning_columns: list[_AliasedExpr] = field(factory=list)

    def from_(self, table: str) -> Self:
        """Specify the table to delete from."""
        self.table = table
        return self

    def where(
        self, *conditions: str | tuple[str, Any] | tuple[str, Any, Any] | _Condition
    ) -> Self:
        """Add WHERE clause to the delete statement."""
        for condition in conditions:
            if isinstance(condition, _Condition):
                self.where_expressions.append(condition)
            else:
                self.where_expressions.append(_Condition.from_arg(condition))
        return self

    def returning(self, *columns: str | tuple[str, str]) -> Self:
        """Add a RETURNING clause to the delete statement."""
        self.returning_columns.extend(
            _AliasedExpr.from_arg(column) for column in columns
        )
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
        params = []
        for condition in self.where_expressions:
            params.extend(condition.params)
        return tuple(params)


# Select helper constants for mapping fields to columns in repositories

ACCOUNT_COLUMNS = ("id", "name", "institution", ("created_at", "created"), "properties")
"""Mapping of AccountPublic attributes to database column names for accounts."""

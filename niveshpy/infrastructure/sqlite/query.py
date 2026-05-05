"""Query Builder for SQLite."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import Enum
from typing import Any, Literal, NewType, Self

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


def or_(*conditions: str | tuple[str, Any] | tuple[str, Any, Any]) -> _Condition:
    """Combine conditions with OR, wrapped in parentheses."""
    parsed = [_Condition.from_arg(c) for c in conditions]
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
        *on: str | tuple[str, Any] | tuple[str, Any, Any] | _Condition,
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

    def where(
        self, *conditions: str | tuple[str, Any] | tuple[str, Any, Any] | _Condition
    ) -> Self:
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

    def having(
        self, *conditions: str | tuple[str, Any] | tuple[str, Any, Any] | _Condition
    ) -> Self:
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

"""Database query utilities."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum, auto

from niveshpy.core.query import ast
from niveshpy.core.query.ast import FilterNode


class ResultFormat(StrEnum):
    """Result format options."""

    POLARS = auto()
    SINGLE = auto()
    LIST = auto()


@dataclass
class QueryOptions:
    """Options for querying the database."""

    filters: Iterable[FilterNode] | None = None
    limit: int | None = None
    offset: int | None = None


DEFAULT_QUERY_OPTIONS = QueryOptions()


class UnmappedFieldError(ValueError):
    """Error raised when a field is not mapped to a database column."""

    pass


def prepare_where_clause(operator: ast.Operator, column: str) -> str:
    """Prepare a SQL WHERE clause based on the operator and column.

    Args:
        operator (ast.Operator): The operator to use in the WHERE clause.
        column (str): The database column name.

    Returns:
        str: The SQL WHERE clause.
    """
    match operator:
        case ast.Operator.REGEX_MATCH:
            return f"regexp_matches({column}, ?, 'i')"
        case ast.Operator.NOT_REGEX_MATCH:
            return f"NOT regexp_matches({column}, ?, 'i')"
        case ast.Operator.EQUALS:
            return f"{column} = ?"
        case ast.Operator.NOT_EQUALS:
            return f"{column} != ?"
        case ast.Operator.GREATER_THAN:
            return f"{column} > ?"
        case ast.Operator.GREATER_THAN_EQ:
            return f"{column} >= ?"
        case ast.Operator.LESS_THAN:
            return f"{column} < ?"
        case ast.Operator.LESS_THAN_EQ:
            return f"{column} <= ?"
        case ast.Operator.BETWEEN:
            return f"{column} BETWEEN ? AND ?"
        case ast.Operator.NOT_BETWEEN:
            return f"{column} NOT BETWEEN ? AND ?"
        case ast.Operator.IN:
            return f"{column} IN ?"
        case ast.Operator.NOT_IN:
            return f"{column} NOT IN ?"
        case _:
            raise ValueError(f"Unsupported operator for WHERE clause: {operator}")


def prepare_query_filters(
    filters: Iterable[FilterNode], column_mappings: dict[ast.Field, list[str]]
) -> tuple[str, tuple]:
    """Prepare query filters for database querying.

    Args:
        filters (list): List of FilterNode objects.
        column_mappings (dict): Mapping of AST fields to database column names.

    Returns:
        tuple: A tuple containing the prepared SQL WHERE clause and parameters.
    """
    where_clauses: list[str] = []
    params: list = []

    negative_clauses: list[str] = []
    negative_params: list = []

    date_where_clauses: list[str] = []
    date_params: list[date] = []

    amount_where_clauses: list[str] = []
    amount_params: list[Decimal] = []

    type_where_clauses: list[str] = []
    type_params: list[str] = []

    desc_where_clauses: list[str] = []
    desc_params: list[str] = []

    acc_where_clauses: list[str] = []
    acc_params: list[str] = []

    sec_where_clauses: list[str] = []
    sec_params: list[str] = []

    for filter_node in filters:
        columns = column_mappings.get(filter_node.field, [])
        if not columns:
            raise UnmappedFieldError(
                f"Field {filter_node.field} not mapped to any column."
            )
        match filter_node:
            case FilterNode(
                field=field,
                operator=ast.Operator.NOT_REGEX_MATCH
                | ast.Operator.NOT_EQUALS
                | ast.Operator.NOT_IN
                | ast.Operator.NOT_BETWEEN as op,
                value=v,
            ):
                for col in columns:
                    where_clause = prepare_where_clause(filter_node.operator, col)
                    negative_clauses.append(where_clause)
                    match op:
                        case ast.Operator.NOT_BETWEEN if (
                            isinstance(v, tuple) and len(v) == 2
                        ):
                            negative_params.extend(v)
                        case ast.Operator.NOT_IN if isinstance(v, tuple):
                            negative_params.append(v)
                        case ast.Operator.NOT_REGEX_MATCH | ast.Operator.NOT_EQUALS:
                            negative_params.append(v)
                        case _:
                            raise ValueError(
                                f"Invalid operator - value combination for negative filter: {op} - {v}"
                            )

            case FilterNode(field=ast.Field.DATE, operator=op, value=v):
                for col in columns:
                    where_clause = prepare_where_clause(op, col)
                    date_where_clauses.append(where_clause)
                    match op:
                        case ast.Operator.BETWEEN | ast.Operator.NOT_BETWEEN if (
                            isinstance(v, tuple) and len(v) == 2
                        ):
                            date_params.extend(v)  # type: ignore[arg-type]
                        case ast.Operator.IN | ast.Operator.NOT_IN if isinstance(
                            v, tuple
                        ):
                            date_params.append(v)  # type: ignore[arg-type]
                        case (
                            ast.Operator.EQUALS
                            | ast.Operator.NOT_EQUALS
                            | ast.Operator.GREATER_THAN
                            | ast.Operator.GREATER_THAN_EQ
                            | ast.Operator.LESS_THAN
                            | ast.Operator.LESS_THAN_EQ
                        ) if isinstance(v, date):
                            date_params.append(v)
                        case _:
                            raise ValueError(
                                f"Invalid operator - value combination for date filter: {op} - {v}"
                            )

            case FilterNode(field=ast.Field.AMOUNT, operator=op, value=v):
                for col in columns:
                    where_clause = prepare_where_clause(op, col)
                    amount_where_clauses.append(where_clause)
                    match op:
                        case ast.Operator.BETWEEN | ast.Operator.NOT_BETWEEN if (
                            isinstance(v, tuple) and len(v) == 2
                        ):
                            amount_params.extend(v)  # type: ignore[arg-type]
                        case ast.Operator.IN | ast.Operator.NOT_IN if isinstance(
                            v, tuple
                        ):
                            amount_params.append(v)  # type: ignore[arg-type]
                        case (
                            ast.Operator.EQUALS
                            | ast.Operator.NOT_EQUALS
                            | ast.Operator.GREATER_THAN
                            | ast.Operator.GREATER_THAN_EQ
                            | ast.Operator.LESS_THAN
                            | ast.Operator.LESS_THAN_EQ
                        ) if isinstance(v, Decimal):
                            amount_params.append(v)
                        case _:
                            raise ValueError(
                                f"Invalid operator - value combination for amount filter: {op} - {v}"
                            )

            case FilterNode(field=field, operator=ast.Operator.REGEX_MATCH, value=v):
                for col in columns:
                    where_clause = prepare_where_clause(ast.Operator.REGEX_MATCH, col)
                    match field:
                        case ast.Field.TYPE if isinstance(v, str):
                            type_where_clauses.append(where_clause)
                            type_params.append(v)
                        case ast.Field.DESCRIPTION if isinstance(v, str):
                            desc_where_clauses.append(where_clause)
                            desc_params.append(v)
                        case ast.Field.ACCOUNT if isinstance(v, str):
                            acc_where_clauses.append(where_clause)
                            acc_params.append(v)
                        case ast.Field.SECURITY if isinstance(v, str):
                            sec_where_clauses.append(where_clause)
                            sec_params.append(v)
                        case _:
                            raise ValueError(
                                f"Invalid field - value combination for regex match filter: {field} - {v}"
                            )

            case _:
                raise ValueError(f"Unsupported filter node: {filter_node}")

    where_clauses.extend(negative_clauses)
    params.extend(negative_params)

    if date_where_clauses:
        where_clauses.append(f"({' OR '.join(date_where_clauses)})")
        params.extend(date_params)

    if amount_where_clauses:
        where_clauses.append(f"({' OR '.join(amount_where_clauses)})")
        params.extend(amount_params)

    if type_where_clauses:
        where_clauses.append(f"({' OR '.join(type_where_clauses)})")
        params.extend(type_params)

    if desc_where_clauses:
        where_clauses.append(f"({' OR '.join(desc_where_clauses)})")
        params.extend(desc_params)

    if acc_where_clauses:
        where_clauses.append(f"({' OR '.join(acc_where_clauses)})")
        params.extend(acc_params)

    if sec_where_clauses:
        where_clauses.append(f"({' OR '.join(sec_where_clauses)})")
        params.extend(sec_params)

    return " AND ".join(where_clauses), tuple(params)

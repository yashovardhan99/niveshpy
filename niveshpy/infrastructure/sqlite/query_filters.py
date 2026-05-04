"""Functions to convert prepared filter nodes into SQLAlchemy filter expressions."""

from collections.abc import Container, Iterable

from sqlalchemy import column, func
from sqlalchemy.sql.expression import ColumnClause, ColumnElement, or_

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.exceptions import OperationError, QuerySyntaxError


def prepare_expression(filter: FilterNode, column: ColumnClause) -> ColumnElement[bool]:
    """Prepare a SQLAlchemy expression for a given filter and column.

    Args:
        filter (FilterNode): The filter node to prepare.
        column (str): The database column name.

    Returns:
        ColumnElement[bool]: The prepared SQLAlchemy expression.
    """
    op = filter.operator
    match op:
        case Operator.REGEX_MATCH if isinstance(filter.value, str):
            return func.iregexp(filter.value, column)
        case Operator.NOT_REGEX_MATCH if isinstance(filter.value, str):
            return ~func.iregexp(filter.value, column)
        case Operator.EQUALS:
            return column == filter.value
        case Operator.NOT_EQUALS:
            return column != filter.value
        case Operator.GREATER_THAN:
            return column > filter.value
        case Operator.GREATER_THAN_EQ:
            return column >= filter.value
        case Operator.LESS_THAN:
            return column < filter.value
        case Operator.LESS_THAN_EQ:
            return column <= filter.value
        case Operator.BETWEEN if (
            isinstance(filter.value, tuple) and len(filter.value) == 2
        ):
            return column.between(filter.value[0], filter.value[1])
        case Operator.NOT_BETWEEN if (
            isinstance(filter.value, tuple) and len(filter.value) == 2
        ):
            return ~column.between(filter.value[0], filter.value[1])
        case Operator.IN if isinstance(filter.value, tuple):
            return column.in_(filter.value)
        case Operator.NOT_IN if isinstance(filter.value, tuple):
            return ~column.in_(filter.value)
        case _:
            raise OperationError(
                f"Unsupported operator / value for WHERE clause: {op} / {filter.value}"
            )


def get_sqlalchemy_filters(
    filters: Iterable[FilterNode],
    column_mappings: dict[Field, list],
    include_fields: Container[Field] | None = None,
) -> list[ColumnElement[bool]]:
    """Convert prepared filter nodes into SQLAlchemy filter expressions.

    Args:
        filters (Iterable[FilterNode]): The prepared filter nodes to convert.
        column_mappings (dict[Field, list]): A mapping of Field enums to database column
            names or SQLAlchemy column objects.
        include_fields (Container[Field], optional): An optional set of fields to include
            in the output. If provided, only filters for these fields will be processed.

    Returns:
        list[ColumnElement[bool]]: A list of SQLAlchemy filter expressions to be used in a WHERE clause.
    """
    # Regex expressions for text search
    text_expressions: list[ColumnElement[bool]] = []

    # All expressions
    expressions: list[ColumnElement[bool]] = []

    for filter in filters:
        cols = column_mappings.get(filter.field, [])

        if include_fields is not None and filter.field not in include_fields:
            # Skip this filter as its field is not in the included fields
            continue

        if not cols:
            raise QuerySyntaxError(
                str(filter), f"Field {filter.field} not mapped to any column."
            )

        col_expressions: list[ColumnElement[bool]] = []
        for col in cols:
            col_expressions.append(
                prepare_expression(filter, column(col) if isinstance(col, str) else col)
            )
        if filter.operator in {Operator.REGEX_MATCH, Operator.NOT_REGEX_MATCH}:
            text_expressions.extend(col_expressions)
        else:
            expressions.append(or_(*col_expressions))

    if text_expressions:
        expressions.append(or_(*text_expressions))

    return expressions

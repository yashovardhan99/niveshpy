"""Module for preparing query AST nodes for evaluation."""

import itertools
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace

from sqlmodel import column, func
from sqlmodel.sql.expression import ColumnClause, ColumnElement, or_

from niveshpy.core.query import ast
from niveshpy.core.query.ast import Field, FilterNode, FilterValue, Operator
from niveshpy.core.query.parser import QueryParser
from niveshpy.core.query.tokenizer import QueryLexer
from niveshpy.exceptions import OperationError, QuerySyntaxError


def prepare_filters(
    filters: Iterable[FilterNode], default_field: Field
) -> list[FilterNode]:
    """Prepare and optimize the list of filter nodes for evaluation.

    This function applies optimizations such as combining filters of the same field
    and operator into a single filter where applicable.

    Args:
        filters (list): List of FilterNode objects.
        default_field (Field): The default field to replace DEFAULT field nodes.

    Returns:
        list: The prepared list of FilterNode objects.
    """
    grouped = group_filters(filters, default_field)
    # print("Grouped filters:", grouped.items())
    combined = []

    for field, field_filters in grouped.items():
        combined.extend(combine_filters(field, field_filters))

    # print("Combined filters:", combined)

    return combined


def combine_filters(field: Field, filters: Iterable[FilterNode]) -> list[FilterNode]:
    """Combine multiple filters of comparable operator into a single filter.

    This function combines filters that can be logically merged, such as multiple
    equality checks into an IN operator.

    Args:
        field (Field): The field of the filters to combine.
        filters (list): List of FilterNode objects.

    Returns:
        list: The combined list of FilterNode objects.
    """
    combined_filters: dict[Operator, list[FilterNode]] = defaultdict(list)
    other_filters: list[FilterNode] = []

    for filter_node in filters:
        if filter_node.operator in COMBINED:
            combined_filters[COMBINED[filter_node.operator]].append(filter_node)
        else:
            other_filters.append(filter_node)

    results = other_filters.copy()

    for operator, ops_filters in combined_filters.items():
        values: list[FilterValue] = []
        for f in ops_filters:
            if isinstance(f.value, tuple):
                values.extend(f.value)
            else:
                values.append(f.value)
        results.append(
            FilterNode(
                field=field,
                operator=operator,
                value=tuple(values),  # type: ignore[arg-type]
            )
        )

    return results


def group_filters(
    filters: Iterable[FilterNode], default_field: Field
) -> dict[Field, list[FilterNode]]:
    """Group filters by field."""
    grouped_filters: dict[Field, list[FilterNode]] = defaultdict(list)
    for filter_node in filters:
        if filter_node.field == Field.DEFAULT:
            filter_node = replace(filter_node, field=default_field)
            grouped_filters[default_field].append(filter_node)
        else:
            grouped_filters[filter_node.field].append(filter_node)
    return grouped_filters


COMBINED = {
    Operator.IN: Operator.IN,
    Operator.NOT_IN: Operator.NOT_IN,
    Operator.EQUALS: Operator.IN,
    Operator.NOT_EQUALS: Operator.NOT_IN,
}


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
        case ast.Operator.REGEX_MATCH if isinstance(filter.value, str):
            return func.iregexp(filter.value, column)
        case ast.Operator.NOT_REGEX_MATCH if isinstance(filter.value, str):
            return ~func.iregexp(filter.value, column)
        case ast.Operator.EQUALS:
            return column == filter.value
        case ast.Operator.NOT_EQUALS:
            return column != filter.value
        case ast.Operator.GREATER_THAN:
            return column > filter.value
        case ast.Operator.GREATER_THAN_EQ:
            return column >= filter.value
        case ast.Operator.LESS_THAN:
            return column < filter.value
        case ast.Operator.LESS_THAN_EQ:
            return column <= filter.value
        case ast.Operator.BETWEEN if (
            isinstance(filter.value, tuple) and len(filter.value) == 2
        ):
            return column.between(filter.value[0], filter.value[1])
        case ast.Operator.NOT_BETWEEN if (
            isinstance(filter.value, tuple) and len(filter.value) == 2
        ):
            return ~column.between(filter.value[0], filter.value[1])
        case ast.Operator.IN if isinstance(filter.value, tuple):
            return column.in_(filter.value)
        case ast.Operator.NOT_IN if isinstance(filter.value, tuple):
            return ~column.in_(filter.value)
        case _:
            raise OperationError(
                f"Unsupported operator / value for WHERE clause: {op} / {filter.value}"
            )


def get_filters_from_queries(
    queries: tuple[str, ...],
    default_field: Field,
    column_mappings: dict[Field, list],
) -> list[ColumnElement[bool]]:
    """Convert query strings into a combined SQLAlchemy filter expression.

    Args:
        queries (tuple): Tuple of query strings.
        default_field (Field): The default field to use for filters.
        column_mappings (dict): Mapping of Fields to database column names.

    Returns:
        list: The list of SQLAlchemy filter expressions.
    """
    try:
        stripped_queries = map(str.strip, queries)
        lexers = map(QueryLexer, stripped_queries)
        parsers = map(QueryParser, lexers)
        filters: Iterable[FilterNode] = itertools.chain.from_iterable(
            map(QueryParser.parse, parsers)
        )
        filters = prepare_filters(filters, default_field)
    except QuerySyntaxError as e:
        e.add_note(f"Error was reported on input: {e.input_value}")
        raise QuerySyntaxError(" ".join(queries), cause=e.cause) from e

    expressions: list[ColumnElement[bool]] = []
    for filter in filters:
        cols = column_mappings.get(filter.field, [])
        if not cols:
            raise QuerySyntaxError(
                " ".join(queries), f"Field {filter.field} not mapped to any column."
            )

        col_expressions: list[ColumnElement[bool]] = []
        for col in cols:
            col_expressions.append(
                prepare_expression(filter, column(col) if isinstance(col, str) else col)
            )
        expressions.append(or_(*col_expressions))

    return expressions


def get_fields_from_queries(
    queries: tuple[str, ...],
) -> set[Field]:
    """Extract fields used in the query strings.

    Args:
        queries (tuple): Tuple of query strings.

    Returns:
        set: The set of Fields used in the queries.
    """
    try:
        stripped_queries = map(str.strip, queries)
        lexers = map(QueryLexer, stripped_queries)
        parsers = map(QueryParser, lexers)
        filters: list[FilterNode] = list(
            itertools.chain.from_iterable(map(QueryParser.parse, parsers))
        )
    except QuerySyntaxError as e:
        e.add_note(f"Error was reported on input: {e.input_value}")
        raise QuerySyntaxError(" ".join(queries), cause=e.cause) from e

    used_fields: set[Field] = set()
    for filter in filters:
        used_fields.add(filter.field)

    return used_fields

"""Functions to convert prepared filter nodes into sqlite filter expressions."""

from collections.abc import Container, Iterable, Mapping, Sequence

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.exceptions import OperationError, QuerySyntaxError
from niveshpy.infrastructure.sqlite.query import ConditionType, Query, in_, not_in, or_


def prepare_expression(filter: FilterNode, column: str) -> ConditionType:
    """Prepare a condition expression for a given filter and column.

    Args:
        filter (FilterNode): The filter node to prepare.
        column (str): The database column name.

    Returns:
        ConditionType: The prepared condition expression.
    """
    op = filter.operator
    match op:
        case Operator.REGEX_MATCH if isinstance(filter.value, str):
            return f"IREGEXP(?, {column})", filter.value
        case Operator.NOT_REGEX_MATCH if isinstance(filter.value, str):
            return f"NOT IREGEXP(?, {column})", filter.value
        case Operator.EQUALS:
            return f"{column} = ?", filter.value
        case Operator.NOT_EQUALS:
            return f"{column} != ?", filter.value
        case Operator.GREATER_THAN:
            return f"{column} > ?", filter.value
        case Operator.GREATER_THAN_EQ:
            return f"{column} >= ?", filter.value
        case Operator.LESS_THAN:
            return f"{column} < ?", filter.value
        case Operator.LESS_THAN_EQ:
            return f"{column} <= ?", filter.value
        case Operator.BETWEEN if (
            isinstance(filter.value, tuple) and len(filter.value) == 2
        ):
            return f"{column} BETWEEN ? AND ?", filter.value[0], filter.value[1]
        case Operator.NOT_BETWEEN if (
            isinstance(filter.value, tuple) and len(filter.value) == 2
        ):
            return f"{column} NOT BETWEEN ? AND ?", filter.value[0], filter.value[1]
        case Operator.IN if isinstance(filter.value, tuple):
            return in_(column, *filter.value)
        case Operator.NOT_IN if isinstance(filter.value, tuple):
            return not_in(column, *filter.value)
        case _:
            raise OperationError(
                f"Unsupported operator / value for WHERE clause: {op} / {filter.value}"
            )


def generate_query_from_filters(
    filters: Iterable[FilterNode],
    column_mappings: Mapping[Field, Sequence[str]],
    include_fields: Container[Field] | None = None,
) -> Query:
    """Convert prepared filter nodes into sql filter expressions.

    Args:
        filters (Iterable[FilterNode]): The prepared filter nodes to convert.
        column_mappings (Mapping[Field, Sequence[str]]): A mapping of Field enums to
            column names.
        include_fields (Container[Field], optional): An optional set of fields to include
            in the output. If provided, only filters for these fields will be processed.

    Returns:
        Query: A Query object representing the SQL filter expressions.
    """
    query = Query()
    expression_by_fields: dict[Field, ConditionType] = {}
    for filter in filters:
        cols = column_mappings.get(filter.field, [])

        if include_fields is not None and filter.field not in include_fields:
            # Skip this filter as its field is not in the included fields
            continue

        if not cols:
            raise QuerySyntaxError(
                str(filter), f"Field {filter.field} not mapped to any column."
            )

        col_expressions: list[ConditionType] = []
        for col in cols:
            col_expressions.append(prepare_expression(filter, col))

        if filter.field in expression_by_fields:
            # Combine with existing expression for this field using OR
            expression_by_fields[filter.field] = or_(
                expression_by_fields[filter.field], or_(*col_expressions)
            )
        else:
            expression_by_fields[filter.field] = or_(*col_expressions)

    return query.where(*expression_by_fields.values())

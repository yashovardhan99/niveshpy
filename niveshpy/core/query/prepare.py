"""Module for preparing query AST nodes for evaluation."""

from collections import defaultdict
from dataclasses import replace
from niveshpy.core.query.ast import Field, FilterNode, FilterValue, Operator


def prepare_filters(
    filters: list[FilterNode], default_field: Field
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


def combine_filters(field: Field, filters: list[FilterNode]) -> list[FilterNode]:
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
    filters: list[FilterNode], default_field: Field
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

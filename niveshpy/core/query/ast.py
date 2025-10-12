"""Module defining the AST nodes for the query parser."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum, auto


class Field(Enum):
    """Enumeration of possible fields in the query AST."""

    ACCOUNT = auto()
    AMOUNT = auto()
    DATE = auto()
    DESCRIPTION = auto()
    SECURITY = auto()
    TYPE = auto()
    DEFAULT = auto()  # Default field when none is specified


class Operator(Enum):
    """Enumeration of possible operators in the query AST."""

    REGEX_MATCH = auto()
    NOT_REGEX_MATCH = auto()
    EQUALS = auto()
    NOT_EQUALS = auto()
    GREATER_THAN = auto()
    GREATER_THAN_EQ = auto()
    LESS_THAN = auto()
    LESS_THAN_EQ = auto()
    BETWEEN = auto()
    NOT_BETWEEN = auto()
    IN = auto()
    NOT_IN = auto()

    def negate(self) -> "Operator":
        """Return the negated version of the operator."""
        return {
            Operator.EQUALS: Operator.NOT_EQUALS,
            Operator.NOT_EQUALS: Operator.EQUALS,
            Operator.GREATER_THAN: Operator.LESS_THAN_EQ,
            Operator.GREATER_THAN_EQ: Operator.LESS_THAN,
            Operator.LESS_THAN: Operator.GREATER_THAN_EQ,
            Operator.LESS_THAN_EQ: Operator.GREATER_THAN,
            Operator.BETWEEN: Operator.NOT_BETWEEN,
            Operator.NOT_BETWEEN: Operator.BETWEEN,
            Operator.IN: Operator.NOT_IN,
            Operator.NOT_IN: Operator.IN,
            Operator.REGEX_MATCH: Operator.NOT_REGEX_MATCH,
            Operator.NOT_REGEX_MATCH: Operator.REGEX_MATCH,
        }.get(self, self)


FilterValue = (
    str | tuple[str, ...] | Decimal | tuple[Decimal, ...] | date | tuple[date, ...]
)


@dataclass(slots=True, frozen=True)
class FilterNode:
    """Class representing a filter node in the query AST."""

    field: Field
    operator: Operator
    value: FilterValue

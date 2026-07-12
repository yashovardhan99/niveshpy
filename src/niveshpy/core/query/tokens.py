"""Module for query token types."""

from dataclasses import dataclass
from enum import Enum


class Token:
    """Base class for all token types."""


@dataclass(slots=True)
class End(Token):
    """Token representing the end of input."""


@dataclass(slots=True)
class Colon(Token):
    """Token representing a colon (:) character."""


@dataclass(slots=True)
class Dash(Token):
    """Token representing a dash (-) character."""


@dataclass(slots=True)
class Dot(Token):
    """Token representing a dot (.) character."""


@dataclass(slots=True)
class RangeSeparator(Token):
    """Token representing a range separator (..) string."""


@dataclass(slots=True)
class Gt(Token):
    """Token representing greater than (>) character."""


@dataclass(slots=True)
class GtEq(Token):
    """Token representing greater than or equal to (>=) characters."""


@dataclass(slots=True)
class Lt(Token):
    """Token representing less than (<) character."""


@dataclass(slots=True)
class LtEq(Token):
    """Token representing less than or equal to (<=) characters."""


class Keyword(Token, Enum):
    """Token representing a keyword (e.g., field names)."""

    Account = "acct"
    Amount = "amt"
    Date = "date"
    Description = "desc"
    Security = "sec"
    Type = "type"
    Not = "not"


@dataclass(slots=True, frozen=True)
class Literal(Token):
    """Token representing a literal value."""

    value: str


@dataclass(slots=True, frozen=True)
class Int(Token):
    """Token representing an integer."""

    value: str


@dataclass(slots=True, frozen=True)
class Unknown(Token):
    """Token representing an unknown or unrecognized character."""

    char: str
    position: int

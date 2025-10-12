"""Module for parsing user queries into structured filters."""

from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from decimal import Decimal
from niveshpy.core.query import tokens as Tokens, ast
from niveshpy.core.query.tokenizer import QueryLexer
import itertools


class QueryParser:
    """Class to parse a user query into structured filters."""

    def __init__(self, lexer: QueryLexer):
        """Initialize with a QueryLexer instance."""
        self.lexer = lexer

    @staticmethod
    def convert_to_string(tokens: Iterable[Tokens.Token]) -> str:
        """Convert a sequence of tokens to a string."""
        strings = []
        for tok in tokens:
            match tok:
                case Tokens.Colon():
                    strings.append(":")
                case Tokens.Dash():
                    strings.append("-")
                case Tokens.Dot():
                    strings.append(".")
                case Tokens.RangeSeparator():
                    strings.append("..")
                case Tokens.Gt():
                    strings.append(">")
                case Tokens.GtEq():
                    strings.append(">=")
                case Tokens.Lt():
                    strings.append("<")
                case Tokens.LtEq():
                    strings.append("<=")
                case Tokens.Keyword(value=kw_value):
                    strings.append(kw_value)
                case Tokens.Literal(value=lit_value):
                    strings.append(lit_value)
                case Tokens.Int(value=int_value):
                    strings.append(str(int_value))
                case Tokens.Unknown(char=char):
                    strings.append(char)
                case _:
                    raise ValueError(
                        f"Invalid token {tok} in sequence {tokens} for string conversion."
                    )
        return "".join(strings)

    @staticmethod
    def convert_to_number(tokens: Iterable[Tokens.Token]) -> Decimal:
        """Convert a sequence of tokens to a Decimal number."""
        match tokens:
            case [
                Tokens.Dash(),
                Tokens.Int(value=int_value),
                Tokens.Dot(),
                Tokens.Int(value=frac_value),
            ]:  # Negative fractional number
                return Decimal(f"-{int_value}.{frac_value}")
            case [
                Tokens.Int(value=int_value),
                Tokens.Dot(),
                Tokens.Int(value=frac_value),
            ]:  # Positive fractional number
                return Decimal(f"{int_value}.{frac_value}")
            case [
                Tokens.Dash(),
                Tokens.Int(value=int_value),
            ]:  # Negative integer
                return Decimal(f"-{int_value}")
            case [Tokens.Int(value=int_value)]:  # Positive integer
                return Decimal(int_value)
            case _:
                raise ValueError(
                    f"Invalid token sequence {tokens} for number conversion."
                )
        raise NotImplementedError("Conversion to number not implemented yet.")

    @staticmethod
    def convert_to_date(tokens: Iterable[Tokens.Token], start: bool = True) -> date:
        """Convert a sequence of tokens to a date."""
        match tokens:
            case [
                Tokens.Int(value=year),
                Tokens.Dash(),
                Tokens.Int(value=month),
                Tokens.Dash(),
                Tokens.Int(value=day),
            ]:
                return date(year=int(year), month=int(month), day=int(day))
            case [
                Tokens.Int(value=year),
                Tokens.Dash(),
                Tokens.Int(value=month),
            ] if start:
                return date(year=int(year), month=int(month), day=1)
            case [
                Tokens.Int(value=year),
                Tokens.Dash(),
                Tokens.Int(value=month),
            ] if not start:
                if int(month) == 12:
                    return date(year=int(year) + 1, month=1, day=1) - timedelta(days=1)
                return date(year=int(year), month=int(month) + 1, day=1) - timedelta(
                    days=1
                )
            case [Tokens.Int(value=year)] if start:
                return date(year=int(year), month=1, day=1)
            case [Tokens.Int(value=year)] if not start:
                return date(year=int(year) + 1, month=1, day=1) - timedelta(days=1)
            case _:
                raise ValueError(
                    f"Invalid token sequence {tokens} for date conversion."
                )
        """Convert a sequence of tokens to a date."""
        raise NotImplementedError("Conversion to date not implemented yet.")

    def read_remaining_as_literal(self) -> str:
        """Read the entire input as a literal string."""
        return QueryParser.convert_to_string(self.get_remaining_tokens())

    def get_remaining_tokens(self) -> list[Tokens.Token]:
        """Get all remaining tokens from the lexer."""
        return list(
            itertools.takewhile(
                lambda t: not isinstance(t, Tokens.End), iter(self.lexer)
            )
        )

    def negate_filters(self, filters: Sequence[ast.FilterNode]) -> list[ast.FilterNode]:
        """Negate the given filters."""
        negated_filters = []
        for filter_node in filters:
            negated_operator = filter_node.operator.negate()
            negated_filters.append(
                ast.FilterNode(
                    field=filter_node.field,
                    operator=negated_operator,
                    value=filter_node.value,
                )
            )
        return negated_filters

    def get_operator_from_token(self, token: Tokens.Token) -> ast.Operator:
        """Map a token to its corresponding AST operator."""
        match token:
            case Tokens.Gt():
                return ast.Operator.GREATER_THAN
            case Tokens.GtEq():
                return ast.Operator.GREATER_THAN_EQ
            case Tokens.Lt():
                return ast.Operator.LESS_THAN
            case Tokens.LtEq():
                return ast.Operator.LESS_THAN_EQ
            case _:
                raise ValueError(f"Token {token} cannot be mapped to an operator.")

    def parse(self) -> list[ast.FilterNode]:
        """Parse the query and return a structured filter."""
        # Implementation of parsing logic goes here
        first_token = self.lexer.next_token()
        field: ast.Field
        operator: ast.Operator
        value: str | Decimal | tuple[Decimal, Decimal] | date | tuple[date, date]

        match first_token:
            case Tokens.Keyword.Not:
                sub_filters = self.parse()
                return self.negate_filters(sub_filters)
            case Tokens.End():
                return []  # No filters

            case Tokens.Keyword.Amount:
                field = ast.Field.AMOUNT
                tokens = self.get_remaining_tokens()
                match tokens:
                    case [
                        (
                            Tokens.Gt() | Tokens.GtEq() | Tokens.Lt() | Tokens.LtEq()
                        ) as op,
                        *value_tokens,
                    ]:  # Inequality comparison
                        operator = self.get_operator_from_token(op)
                        value = self.convert_to_number(value_tokens)

                    case _ if Tokens.RangeSeparator() in tokens:  # Range expression
                        sep_index = tokens.index(Tokens.RangeSeparator())
                        start_value = self.convert_to_number(tokens[:sep_index])
                        end_value = self.convert_to_number(tokens[sep_index + 1 :])
                        if start_value > end_value:
                            raise ValueError(
                                f"Invalid amount range: start amount {start_value} is greater than end amount {end_value}."
                            )
                        if start_value == end_value:
                            operator = ast.Operator.EQUALS
                            value = start_value
                        else:
                            operator = ast.Operator.BETWEEN
                            value = (start_value, end_value)
                    case _:  # Exact match
                        value = self.convert_to_number(tokens)
                        operator = ast.Operator.EQUALS

            case Tokens.Keyword.Date:
                field = ast.Field.DATE
                tokens = self.get_remaining_tokens()
                if Tokens.RangeSeparator() in tokens:  # Range expression
                    sep_index = tokens.index(Tokens.RangeSeparator())
                    if len(tokens) == 1:  # Only '..' is present
                        raise ValueError(
                            "Both start date and end date cannot be non-empty in a range expression."
                        )

                    start_date = (
                        self.convert_to_date(tokens[:sep_index], start=True)
                        if sep_index > 0
                        else date.min
                    )
                    end_date = (
                        self.convert_to_date(tokens[sep_index + 1 :], start=False)
                        if sep_index < len(tokens) - 1
                        else date.max
                    )
                else:  # Single date
                    start_date = self.convert_to_date(tokens, start=True)
                    end_date = self.convert_to_date(tokens, start=False)

                if start_date == date.min:
                    operator = ast.Operator.LESS_THAN_EQ
                    value = end_date
                elif end_date == date.max:
                    operator = ast.Operator.GREATER_THAN_EQ
                    value = start_date
                elif start_date > end_date:
                    raise ValueError(
                        f"Invalid date range: start date {start_date} is after end date {end_date}."
                    )
                elif start_date == end_date:
                    operator = ast.Operator.EQUALS
                    value = start_date
                else:
                    operator = ast.Operator.BETWEEN
                    value = (start_date, end_date)

            case (
                Tokens.Keyword.Account
                | Tokens.Keyword.Description
                | Tokens.Keyword.Type
                | Tokens.Keyword.Security as kw
            ):
                match kw:
                    case Tokens.Keyword.Account:
                        field = ast.Field.ACCOUNT
                    case Tokens.Keyword.Description:
                        field = ast.Field.DESCRIPTION
                    case Tokens.Keyword.Type:
                        field = ast.Field.TYPE
                    case Tokens.Keyword.Security:
                        field = ast.Field.SECURITY
                operator = ast.Operator.REGEX_MATCH
                value = self.read_remaining_as_literal()

            case _:
                field = ast.Field.DEFAULT
                operator = ast.Operator.REGEX_MATCH
                value = self.convert_to_string(
                    [first_token] + self.get_remaining_tokens()
                )

        return [
            ast.FilterNode(
                field=field,
                operator=operator,
                value=value,
            )
        ]

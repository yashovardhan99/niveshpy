"""Module for tokenizing user queries."""

from niveshpy.core.query import tokens


class QueryLexer:
    """Class to tokenize and parse user queries."""

    def __init__(self, query: str):
        """Initialize with the query string."""
        self.text = query
        self.position = 0
        self.read_position = 0
        self.read_char()

    def read_char(self) -> None:
        """Read the next character and advance the position."""
        if self.read_position >= len(self.text):
            self.chr = ""
        else:
            self.chr = self.text[self.read_position]

        self.position = self.read_position
        self.read_position += 1

    def peek(self) -> str:
        """Peek at the next character without advancing the position."""
        return (
            self.text[self.read_position] if self.read_position < len(self.text) else ""
        )

    def read_literal(self) -> str:
        """Read a literal until a special character is encountered."""
        start_position = self.position
        while (nxt := self.peek()) and nxt != "" and nxt != ":":
            self.read_char()
        return self.text[start_position : self.read_position]

    def read_int(self) -> str:
        """Read an integer from the input."""
        start_position = self.position
        while self.peek().isdigit():
            self.read_char()
        return self.text[start_position : self.read_position]

    def __iter__(self):
        """Return the iterator object."""
        while (token := self.next_token()) and not isinstance(token, tokens.End):
            yield token
        yield token

    def next_token(self) -> tokens.Token:
        """Return the next token from the input."""
        tok: tokens.Token
        match self.chr:
            case "":
                tok = tokens.End()
            case ":":
                tok = tokens.Colon()
            case "-":
                tok = tokens.Dash()
            case ".":
                if self.peek() == ".":
                    self.read_char()
                    tok = tokens.RangeSeparator()
                else:
                    tok = tokens.Dot()
            case ">":
                if self.peek() == "=":
                    self.read_char()
                    tok = tokens.GtEq()
                else:
                    tok = tokens.Gt()
            case "<":
                if self.peek() == "=":
                    self.read_char()
                    tok = tokens.LtEq()
                else:
                    tok = tokens.Lt()
            case t if t.isdigit():
                integer = self.read_int()
                tok = tokens.Int(value=integer)
            case t if t.isalpha():
                word = self.read_literal()
                match word:
                    case "date" if self.peek() == ":":
                        self.read_char()
                        tok = tokens.Keyword.Date
                    case "amt" if self.peek() == ":":
                        self.read_char()
                        tok = tokens.Keyword.Amount
                    case "desc" if self.peek() == ":":
                        self.read_char()
                        tok = tokens.Keyword.Description
                    case "type" if self.peek() == ":":
                        self.read_char()
                        tok = tokens.Keyword.Type
                    case "acct" if self.peek() == ":":
                        self.read_char()
                        tok = tokens.Keyword.Account
                    case "sec" if self.peek() == ":":
                        self.read_char()
                        tok = tokens.Keyword.Security
                    case "not" if self.peek() == ":":
                        self.read_char()
                        tok = tokens.Keyword.Not
                    case _:
                        tok = tokens.Literal(value=word)
            case _:
                tok = tokens.Literal(value=self.read_literal())

        self.read_char()
        return tok

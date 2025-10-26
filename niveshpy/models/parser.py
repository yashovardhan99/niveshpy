"""Model definitions for parsers."""

from dataclasses import dataclass
import datetime
from pathlib import Path
from typing import Protocol
from collections.abc import Iterable


from niveshpy.models.account import AccountRead, AccountWrite
from niveshpy.models.security import SecurityWrite
from niveshpy.models.transaction import TransactionWrite


@dataclass
class ParserInfo:
    """Model for parser metadata."""

    name: str
    """Human-readable name of the parser."""

    description: str
    """Brief description of what the parser does."""

    file_extensions: list[str]
    """List of supported file extensions for the parser (e.g. ['.csv', '.json'])."""

    password_required: bool = False
    """Indicates if the parser requires a password to parse files."""


class Parser(Protocol):
    """Protocol for parser classes."""

    def get_date_range(self) -> tuple[datetime.date, datetime.date]:
        """Get the date range of the parsed data."""
        ...

    def get_accounts(self) -> Iterable[AccountWrite]:
        """Get the list of accounts from the parser."""
        ...

    def get_securities(self) -> Iterable[SecurityWrite]:
        """Get the list of securities from the parser."""
        ...

    def get_transactions(
        self, accounts: Iterable[AccountRead]
    ) -> Iterable[TransactionWrite]:
        """Get the list of transactions from the parser.

        The returned transactions should reference the provided accounts and the securities created earlier.

        Ensure all valid transactions in the (earlier provided) date-range are included.
        The service will overwrite all transactions for the referenced account-security pairs.
        """
        ...


class ParserFactory(Protocol):
    """Protocol for parser factory classes."""

    @classmethod
    def create_parser(
        self, file_path: Path, password: str | None = None, **kwargs
    ) -> Parser:
        """Create a parser instance for the given file."""
        ...

    @classmethod
    def get_parser_info(cls) -> ParserInfo:
        """Get metadata about the parser."""
        ...

    @classmethod
    def can_parse(cls, file_path: Path) -> bool:
        """Check if the parser can handle the given file based on its extension."""
        ...

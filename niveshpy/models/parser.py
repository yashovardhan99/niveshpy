"""Model definitions for parsers."""

import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from niveshpy.models.account import (
    AccountCreate,
    AccountPublic,
)
from niveshpy.models.security import SecurityCreate
from niveshpy.models.transaction import TransactionCreate


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
        """Get the date range of the parsed data.

        Returns:
            A tuple containing the start and end dates of the data.
        """
        ...

    def get_accounts(self) -> Iterable[AccountCreate]:
        """Get the list of accounts from the parser.

        Returns:
            An iterable of AccountCreate objects representing the accounts found in the data.
        """
        ...

    def get_securities(self) -> Iterable[SecurityCreate]:
        """Get the list of securities from the parser.

        Returns:
            An iterable of SecurityCreate objects representing the securities found in the data.
        """
        ...

    def get_transactions(
        self, accounts: Iterable[AccountPublic]
    ) -> Iterable[TransactionCreate]:
        """Get the list of transactions from the parser.

        The returned transactions should reference the provided accounts and the securities created earlier.

        Ensure all valid transactions in the (earlier provided) date-range are included.
        The service will overwrite all transactions for the referenced account-security pairs.

        Args:
            accounts: An iterable of AccountPublic objects representing the accounts to reference.

        Returns:
            An iterable of TransactionCreate objects representing the transactions found in the data.
        """
        ...


class ParserFactory(Protocol):
    """Protocol for parser factory classes."""

    @classmethod
    def create_parser(
        self, file_path: Path, password: str | None = None, **kwargs
    ) -> Parser:
        """Create a parser instance for the given file.

        Returns:
            An instance of a Parser that can handle the given file.
        """
        ...

    @classmethod
    def get_parser_info(cls) -> ParserInfo:
        """Get metadata about the parser.

        Returns:
            A ParserInfo object containing metadata about the parser.
        """
        ...

"""Model definitions for parsers."""

from typing import Protocol
from collections.abc import Iterable

import polars as pl

from niveshpy.models.account import AccountWrite
from niveshpy.models.security import Security
from niveshpy.models.transaction import Transaction


class Parser(Protocol):
    """Protocol for parser classes."""

    def get_accounts(self) -> Iterable[AccountWrite]:
        """Get the list of accounts from the parser."""
        ...

    def get_securities(self) -> Iterable[Security]:
        """Get the list of securities from the parser."""
        ...

    def get_transactions(self) -> Iterable[Transaction] | pl.DataFrame:
        """Get the list of transactions from the parser."""
        ...

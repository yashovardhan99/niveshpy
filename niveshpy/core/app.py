"""Main application class to hold state for the CLI."""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from niveshpy.core.logging import logger
from niveshpy.domain.repositories import AccountRepository

if TYPE_CHECKING:
    from niveshpy.models.parser import Parser
    from niveshpy.services.account import AccountService
    from niveshpy.services.parsing import ParsingService
    from niveshpy.services.price import PriceService
    from niveshpy.services.security import SecurityService
    from niveshpy.services.transaction import TransactionService


class Application:
    """Main application class to hold state for the CLI."""

    def __init__(self) -> None:
        """Initialize the application with its services."""
        from niveshpy.database import initialize as initialize_database

        logger.info("Initializing application")
        initialize_database()
        self._security: SecurityService | None = None
        self._account: AccountService | None = None
        self._transaction: TransactionService | None = None
        self._price: PriceService | None = None
        logger.info("Application initialized")

    @property
    def security(self) -> SecurityService:
        """Return the security service."""
        if self._security is None:
            from niveshpy.services.security import SecurityService

            self._security = SecurityService()
        return self._security

    @property
    def account(self) -> AccountService:
        """Return the account service."""
        if self._account is None:
            from niveshpy.services.account import AccountService

            self._account = AccountService(self.account_repository)
        return self._account

    @functools.cached_property
    def account_repository(self) -> AccountRepository:
        """Return the account repository."""
        from niveshpy.infrastructure.sqlite.repositories import SqliteAccountRepository

        return SqliteAccountRepository()

    @property
    def transaction(self) -> TransactionService:
        """Return the transaction service."""
        if self._transaction is None:
            from niveshpy.services.transaction import TransactionService

            self._transaction = TransactionService()
        return self._transaction

    def get_parsing_service(
        self,
        parser: Parser,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ParsingService:
        """Get the parsing service for the given parser key."""
        from niveshpy.services.parsing import ParsingService

        return ParsingService(parser, progress_callback=progress_callback)

    @property
    def price(self) -> PriceService:
        """Return the price service."""
        if self._price is None:
            from niveshpy.services.price import PriceService

            self._price = PriceService()
        return self._price


@dataclass
class AppState:
    """State for the application."""

    debug: bool = False
    no_input: bool = False
    no_color: bool = False

    @functools.cached_property[Application]
    def app(self) -> Application:
        """The main application instance."""
        return Application()

"""Main application class to hold state for the CLI."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING

from attrs import define

from niveshpy.core.logging import logger
from niveshpy.domain.repositories import (
    AccountRepository,
    PriceRepository,
    SecurityRepository,
    TransactionRepository,
)
from niveshpy.domain.services import LotAccountingService
from niveshpy.services.report_service import ReportService

if TYPE_CHECKING:
    from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase
    from niveshpy.models.parser import Parser
    from niveshpy.services.account import AccountService
    from niveshpy.services.parsing import ParsingService
    from niveshpy.services.price import PriceService
    from niveshpy.services.security import SecurityService
    from niveshpy.services.transaction import TransactionService


class Application:
    """Main application container."""

    def __init__(self, debug: bool = False) -> None:
        """Initialize the application container."""
        self._debug = debug

    @functools.cached_property
    def db(self) -> SqliteDatabase:
        """Return the database instance."""
        from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase

        logger.debug("Initializing database connection")

        db = SqliteDatabase(debug=self._debug)
        db.initialize()
        return db

    @functools.cached_property
    def security(self) -> SecurityService:
        """Return the security service."""
        from niveshpy.services.security import SecurityService

        return SecurityService(self.security_repository)

    @functools.cached_property
    def security_repository(self) -> SecurityRepository:
        """Return the security repository."""
        from niveshpy.infrastructure.sqlite.repositories import SqliteSecurityRepository

        return SqliteSecurityRepository(self.db.session_factory)

    @functools.cached_property
    def account(self) -> AccountService:
        """Return the account service."""
        from niveshpy.services.account import AccountService

        return AccountService(self.account_repository)

    @functools.cached_property
    def account_repository(self) -> AccountRepository:
        """Return the account repository."""
        from niveshpy.infrastructure.sqlite.repositories import SqliteAccountRepository

        return SqliteAccountRepository(self.db.session_factory)

    @functools.cached_property
    def transaction(self) -> TransactionService:
        """Return the transaction service."""
        from niveshpy.services.transaction import TransactionService

        return TransactionService(
            transaction_repository=self.transaction_repository,
            account_repository=self.account_repository,
            security_repository=self.security_repository,
            lot_accounting_service=LotAccountingService(),
        )

    @functools.cached_property
    def transaction_repository(self) -> TransactionRepository:
        """Return the transaction repository."""
        from niveshpy.infrastructure.sqlite.repositories import (
            SqliteTransactionRepository,
        )

        return SqliteTransactionRepository(self.db.session_factory)

    def get_parsing_service(
        self,
        parser: Parser,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ParsingService:
        """Get the parsing service for the given parser key."""
        from niveshpy.services.parsing import ParsingService

        return ParsingService(
            parser,
            self.account_repository,
            self.security_repository,
            self.transaction_repository,
            progress_callback=progress_callback,
        )

    @functools.cached_property
    def price_repository(self) -> PriceRepository:
        """Return the price repository."""
        from niveshpy.infrastructure.sqlite.repositories import SqlitePriceRepository

        return SqlitePriceRepository(self.db.session_factory)

    @functools.cached_property
    def price(self) -> PriceService:
        """Return the price service."""
        from niveshpy.services.price import PriceService

        return PriceService(self.price_repository, self.security_repository)

    @functools.cached_property
    def report_service(self) -> ReportService:
        """Return the report service."""
        return ReportService(
            transaction_repository=self.transaction_repository,
            price_repository=self.price_repository,
            security_repository=self.security_repository,
            account_repository=self.account_repository,
            lot_accounting_service=LotAccountingService(),
        )


@define
class AppState:
    """State for the application."""

    debug: bool = False
    no_input: bool = False
    no_color: bool = False

    @functools.cached_property[Application]
    def app(self) -> Application:
        """The main application instance."""
        return Application(self.debug)

"""Model definitions for price providers."""

import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from niveshpy.models.price import PriceData
from niveshpy.models.security import SecurityRead


@dataclass
class ProviderInfo:
    """Model for provider metadata."""

    name: str
    """Human-readable name of the provider."""

    description: str
    """Brief description of what the provider does."""

    supports_historical: bool = True
    """Indicates if the provider can fetch historical price data."""

    supports_latest: bool = True
    """Indicates if the provider can fetch the latest/current price."""

    max_concurrent_requests: int = 0
    """Maximum number of concurrent requests allowed (0 = no limit)."""


class Provider(Protocol):
    """Protocol for price provider classes."""

    def get_priority(self, security: SecurityRead) -> int | None:
        """Get the priority of this provider for the given security.

        Lower numbers = higher priority. Providers are tried in priority order
        when multiple providers can handle the same security.

        Returns:
            An integer representing the priority (e.g., 10, 20, 30).
            Return None if the provider cannot handle the given security.
        """
        ...

    def fetch_latest_price(self, security: SecurityRead) -> PriceData:
        """Fetch the latest price for a security.

        Args:
            security: The security to fetch price for

        Returns:
            PriceData
        """
        ...

    def fetch_historical_prices(
        self,
        security: SecurityRead,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Iterable[PriceData]:
        """Fetch historical prices for a security.

        Args:
            security: The security to fetch prices for
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            An iterable of PriceData objects.
        """
        ...


class ProviderFactory(Protocol):
    """Protocol for provider factory classes."""

    @classmethod
    def create_provider(cls) -> Provider:
        """Create a provider instance.

        Returns:
            An instance of a Provider.
        """
        ...

    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        """Get metadata about the provider.

        Returns:
            A ProviderInfo object containing metadata about the provider.
        """
        ...

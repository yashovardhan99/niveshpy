"""Test provider implementations for PriceService tests."""

import datetime
from decimal import Decimal
from enum import StrEnum, auto

from niveshpy.exceptions import (
    InvalidInputError,
    NetworkError,
    ResourceNotFoundError,
)
from niveshpy.models.price import PriceCreate
from niveshpy.models.provider import ProviderInfo


class ProviderBehavior(StrEnum):
    """Enum for configurable provider behaviors."""

    NORMAL = auto()
    EMPTY = auto()
    NETWORK_ERROR = auto()
    NOT_FOUND = auto()
    VALUE_ERROR = auto()
    NIVESHPY_ERROR = auto()
    RUNTIME_ERROR = auto()
    OLD_DATA = auto()


class ConfigurableProvider:
    """Configurable test provider that can simulate various behaviors."""

    def __init__(
        self,
        priority: int = 10,
        behavior: ProviderBehavior = ProviderBehavior.NORMAL,
        price_count: int = 10,
    ):
        """Initialize configurable provider.

        Args:
            priority: Priority value to return (lower = higher priority).
            behavior: Provider behavior (from ProviderBehavior enum).
            price_count: Number of prices to generate.
        """
        self.priority_value = priority
        self.behavior = behavior
        self.price_count = price_count
        self.call_count = 0

    def get_priority(self, security):
        """Return configured priority for all securities."""
        if security.key.startswith("UNSUPPORTED"):
            return None
        return self.priority_value

    def fetch_historical_prices(self, security, start_date, end_date):
        """Return prices based on configured behavior."""
        self.call_count += 1

        if self.behavior == ProviderBehavior.EMPTY:
            return []

        if self.behavior == ProviderBehavior.NETWORK_ERROR:
            raise NetworkError("Network error")

        if self.behavior == ProviderBehavior.NOT_FOUND:
            raise ResourceNotFoundError("security", security.key)

        if self.behavior == ProviderBehavior.VALUE_ERROR:
            raise ValueError("Unexpected error")

        if self.behavior == ProviderBehavior.NIVESHPY_ERROR:
            raise InvalidInputError("test_value", "Custom NiveshPyError for testing")

        if self.behavior == ProviderBehavior.RUNTIME_ERROR:
            raise RuntimeError("Simulated runtime error")

        if self.behavior == ProviderBehavior.OLD_DATA:
            return [
                PriceCreate(
                    security_key=security.key,
                    date=datetime.date(2000, 1, 1),
                    open=Decimal("100.00"),
                    high=Decimal("100.00"),
                    low=Decimal("100.00"),
                    close=Decimal("100.00"),
                    properties={},
                )
            ]

        # Normal behavior - generate prices
        prices = []
        current_date = start_date
        price = Decimal("100.00")
        days_to_generate = min((end_date - start_date).days + 1, self.price_count)

        for _ in range(days_to_generate):
            prices.append(
                PriceCreate(
                    security_key=security.key,
                    date=current_date,
                    open=price,
                    high=price + Decimal("2.00"),
                    low=price - Decimal("2.00"),
                    close=price + Decimal("1.00"),
                    properties={},
                )
            )
            current_date += datetime.timedelta(days=1)
            price += Decimal("0.50")

        return prices


class ConfigurableProviderFactory:
    """Factory for configurable provider.

    Call configure() before each test to set the desired behavior.
    """

    _priority = 10
    _behavior = ProviderBehavior.NORMAL
    _price_count = 10
    _instance = None

    @classmethod
    def configure(
        cls,
        priority: int = 10,
        behavior: ProviderBehavior = ProviderBehavior.NORMAL,
        price_count: int = 10,
        instance=None,
    ):
        """Configure the provider factory.

        Args:
            priority: Priority value.
            behavior: Provider behavior (from ProviderBehavior enum).
            price_count: Number of prices to generate.
            instance: Pre-configured provider instance (for stateful testing).
        """
        cls._priority = priority
        cls._behavior = behavior
        cls._price_count = price_count
        cls._instance = instance

    @classmethod
    def create_provider(cls):
        """Create a configured provider instance."""
        if cls._instance is not None:
            return cls._instance
        return ConfigurableProvider(
            priority=cls._priority,
            behavior=cls._behavior,
            price_count=cls._price_count,
        )

    @classmethod
    def get_provider_info(cls):
        """Get provider info."""
        behavior_names = {
            ProviderBehavior.NORMAL: "Normal Test Provider",
            ProviderBehavior.EMPTY: "Empty Provider",
            ProviderBehavior.NETWORK_ERROR: "Network Error Provider",
            ProviderBehavior.NOT_FOUND: "Not Found Provider",
            ProviderBehavior.VALUE_ERROR: "Error Provider",
            ProviderBehavior.NIVESHPY_ERROR: "Custom NiveshPyError Provider",
            ProviderBehavior.RUNTIME_ERROR: "Runtime Exception Provider",
            ProviderBehavior.OLD_DATA: "Old Data Provider",
        }

        behavior_descriptions = {
            ProviderBehavior.NORMAL: "Normal test provider",
            ProviderBehavior.EMPTY: "Provider that returns no data",
            ProviderBehavior.NETWORK_ERROR: "Provider that fails with network errors",
            ProviderBehavior.NOT_FOUND: "Provider that raises ResourceNotFoundError",
            ProviderBehavior.VALUE_ERROR: "Provider that raises unexpected errors",
            ProviderBehavior.NIVESHPY_ERROR: "Provider that raises NiveshPyError",
            ProviderBehavior.RUNTIME_ERROR: "Provider that raises RuntimeError",
            ProviderBehavior.OLD_DATA: "Provider that returns old data",
        }

        name = behavior_names.get(cls._behavior, "Test Provider")
        description = behavior_descriptions.get(
            cls._behavior, "Configurable test provider"
        )

        return ProviderInfo(
            name=name,
            description=description,
            supports_historical=True,
            supports_latest=cls._behavior == ProviderBehavior.NORMAL,
            max_concurrent_requests=0,
        )

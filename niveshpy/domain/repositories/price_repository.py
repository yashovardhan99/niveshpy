"""Price repository for NiveshPy."""

import datetime
from collections.abc import Iterable, Sequence
from enum import Enum, auto
from typing import Protocol

from niveshpy.core.query.ast import FilterNode
from niveshpy.models.price import Price, PriceCreate


class PriceFetchProfile(Enum):
    """Enumeration for different price fetch profiles."""

    MINIMAL = auto()
    """Fetch only basic price information (security key, date, open, high, low, close)."""

    WITH_SECURITY = auto()
    """Fetch price information along with related security details."""


class PriceRepository(Protocol):
    """Repository interface for retrieving and managing price data."""

    def get_price_by_key_and_date(
        self,
        security_key: str,
        date: datetime.date,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Price | None:
        """Fetch a price by its security key and date.

        Args:
            security_key: The key of the security to fetch the price for.
            date: The date for which to fetch the price.
            fetch_profile: The profile determining the level of detail to fetch for the price.

        Returns:
            The Price object if found, otherwise None.
        """

    def find_all_prices(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Sequence[Price]:
        """Find all prices matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of Price objects matching the filters and pagination criteria.
        """

    def find_latest_prices(
        self,
        filters: Iterable[FilterNode],
        limit: int | None = None,
        offset: int = 0,
        fetch_profile: PriceFetchProfile = PriceFetchProfile.WITH_SECURITY,
    ) -> Sequence[Price]:
        """Find the latest prices for securities matching the given filters with optional pagination.

        Args:
            filters: An iterable of FilterNode objects to filter prices.
            limit: Optional maximum number of prices to return.
            offset: Optional number of prices to skip before returning results.
            fetch_profile: The profile determining the level of detail to fetch for the prices.

        Returns:
            A sequence of the latest Price objects for securities matching the filters and pagination criteria.
        """

    def overwrite_price(self, price: PriceCreate) -> None:
        """Overwrite an existing price or insert a new one if it doesn't exist.

        Args:
            price: The PriceCreate object containing the price information to overwrite or insert.

        Raises:
            ResourceNotFoundError: If the associated security for the price does not exist in the database.
        """

    def replace_prices_in_range(
        self,
        security_key: str,
        start_date: datetime.date,
        end_date: datetime.date,
        new_prices: Iterable[PriceCreate],
        batch_size: int | None = None,
    ) -> None:
        """Replace all prices for a given security within a specified date range with new prices.

        Args:
            security_key: The key of the security for which to replace prices.
            start_date: The start date of the range for which to replace prices (inclusive).
            end_date: The end date of the range for which to replace prices (inclusive).
            new_prices: An iterable of PriceCreate objects containing the new price information to insert.
            batch_size: Optional batch size for processing the replacement in chunks.
                If None, the replacement will be processed in a single batch.

        Raises:
            ResourceNotFoundError: If the given security key does not exist in the database.
            InvalidInputError: If any of the new prices have dates outside the specified date range,
            have a security key that does not match the given security key, or if there are duplicate
            dates in the new prices.
        """

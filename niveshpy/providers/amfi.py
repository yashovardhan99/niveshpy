"""Provider for mutual fund prices from AMFI."""

import datetime
import decimal
from collections.abc import Iterable

import requests

from niveshpy.exceptions import InvalidSecurityError, PriceNotFoundError
from niveshpy.models.price import PriceDataWrite
from niveshpy.models.provider import ProviderInfo
from niveshpy.models.security import SecurityRead, SecurityType


class AMFIProvider:
    """Provider for mutual fund prices from AMFI."""

    BASE_URL = "https://api.mfapi.in/mf"

    def __init__(self):
        """Initialize the AMFI Provider."""
        self.session = requests.sessions.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_priority(self, security: SecurityRead) -> int | None:
        """Get the priority of this provider for the given security.

        Lower numbers = higher priority. Providers are tried in priority order
        when multiple providers can handle the same security.

        Returns:
            An integer representing the priority (e.g., 10, 20, 30).
            Return None if the provider cannot handle the given security.
        """
        if security.type != SecurityType.MUTUAL_FUND:
            return None
        if security.key.isdigit() and len(security.key) == 6:
            return 15  # Medium priority if key looks like a 6-digit AMFI code
        if security.metadata.get("amfi_code", None) is not None:
            return 10  # Higher priority if AMFI code is provided
        return None  # Cannot handle this security

    def _extract_amfi_code(self, security: SecurityRead) -> str:
        """Extract the AMFI code from the security.

        Args:
            security: The security to extract AMFI code from.

        Returns:
            The AMFI code as a string, or None if not found.
        """
        if security.key.isdigit() and len(security.key) == 6:
            return security.key
        amfi_code = security.metadata.get("amfi_code", None)
        if (
            amfi_code is not None
            and str(amfi_code).isdigit()
            and len(str(amfi_code)) == 6
        ):
            return str(amfi_code)

        raise InvalidSecurityError(
            f"Security {security.key} does not have a valid AMFI code."
        )

    def _extract_price_data(
        self, response: requests.Response, security: SecurityRead
    ) -> Iterable[PriceDataWrite]:
        """Handle the API response and convert it to PriceData instances.

        Args:
            response: The HTTP response from the AMFI API.
            security: The security for which prices are being fetched.

        Returns:
            An iterable of PriceData instances.
        """
        try:
            response.raise_for_status()

            data = response.json()

            price_data_list = data.get("data", [])

            if not price_data_list:
                raise PriceNotFoundError(
                    f"No price data found for security {security.key}.",
                    should_retry=False,
                )

            for item in price_data_list:
                yield PriceDataWrite.from_single_price(
                    security_key=security.key,
                    date=datetime.datetime.strptime(item["date"], "%d-%m-%Y").date(),
                    price=decimal.Decimal(item["nav"]),
                )

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                raise InvalidSecurityError from e
            raise PriceNotFoundError(
                should_retry=True,
            ) from e

    def fetch_latest_price(self, security: SecurityRead) -> PriceDataWrite:
        """Fetch the latest price for a security.

        Args:
            security: The security to fetch price for

        Returns:
            PriceData
        """
        amfi_code = self._extract_amfi_code(security)

        url = f"{self.BASE_URL}/{amfi_code}/latest"
        response = self.session.get(url=url)

        price_data_iter = iter(self._extract_price_data(response, security))

        try:
            return next(price_data_iter)

        except StopIteration:
            raise PriceNotFoundError(
                f"No latest price data found for security {security.key}.",
                should_retry=False,
            ) from None

    def fetch_historical_prices(
        self,
        security: SecurityRead,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Iterable[PriceDataWrite]:
        """Fetch historical prices for a security.

        Args:
            security: The security to fetch prices for
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            An iterable of PriceData objects.
        """
        amfi_code = self._extract_amfi_code(security)

        url = f"{self.BASE_URL}/{amfi_code}"

        payload = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
        }
        response = self.session.get(url=url, params=payload)

        price_data_iter = self._extract_price_data(response, security)

        yield from price_data_iter


class AMFIProviderFactory:
    """Factory for creating AMFIProvider instances."""

    @classmethod
    def create_provider(cls) -> AMFIProvider:
        """Create a provider instance.

        Returns:
            An instance of a Provider.
        """
        return AMFIProvider()

    @classmethod
    def get_provider_info(cls) -> ProviderInfo:
        """Get information about the AMFI provider.

        Returns:
            A dictionary containing provider information.
        """
        return ProviderInfo(
            name="AMFI",
            description="Provider for mutual fund prices from AMFI.",
            supports_historical=True,
            supports_latest=True,
            max_concurrent_requests=0,
        )

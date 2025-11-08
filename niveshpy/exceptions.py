"""Custom exceptions for the NiveshPy library."""


class NiveshPyError(Exception):
    """Base exception class for NiveshPy errors."""

    pass


class PriceProviderError(NiveshPyError):
    """Base class for errors related to price providers."""

    pass


class PriceNotFoundError(PriceProviderError):
    """Exception raised when price data is not found for a security."""

    def __init__(self, *args: object, should_retry: bool = False) -> None:
        """Initialize the PriceNotFoundError.

        Args:
            should_retry: Indicates if the operation that caused this error should be retried.
            *args: Additional arguments to pass to the base Exception class.
        """
        super().__init__(*args)
        self.should_retry = should_retry


class InvalidSecurityError(NiveshPyError):
    """Exception raised when a security is invalid or unsupported.

    If it is not clear whether the security is invalid or just temporarily unsupported,
    consider using PriceNotFoundError instead.
    """

    pass


class ProviderConfigurationError(PriceProviderError):
    """Exception raised for errors in provider configuration.

    This should be raised when the error can be resolved by the user.
    """

    def __init__(self, message: str, *args: object) -> None:
        """Initialize the ProviderConfigurationError.

        Args:
            message: The user-friendly error message.
            *args: Additional arguments to pass to the base Exception class.
        """
        super().__init__(message, *args)
        self.message = message

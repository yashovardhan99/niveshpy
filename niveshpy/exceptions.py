"""Custom exceptions for the NiveshPy library."""


class NiveshPyError(Exception):
    """Base exception class for NiveshPy errors."""


class PriceProviderError(NiveshPyError):
    """Base class for errors related to price providers."""


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


class NiveshPyUserError(NiveshPyError):
    """Exception raised for errors caused by incorrect user input or actions."""

    def __init__(self, message: str, *args: object) -> None:
        """Initialize the NiveshPyUserError.

        Args:
            message: The user-friendly error message.
            *args: Additional arguments to pass to the base Exception class.
        """
        super().__init__(message, *args)
        self.message = message


class NiveshPySystemError(NiveshPyError):
    """Exception raised when a system error occurs."""

    def __init__(self, message: str, *args: object) -> None:
        """Initialize the NiveshPySystemError.

        Args:
            message: The user-friendly error message.
            *args: Additional arguments to pass to the base Exception class.
        """
        super().__init__(message, *args)
        self.message = message

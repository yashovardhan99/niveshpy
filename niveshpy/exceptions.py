"""Custom exceptions for NiveshPy."""


class NiveshPyError(Exception):
    """Base exception class for all NiveshPy errors."""

    def __init__(self, message: str | None = None, *args):
        """Initialize the NiveshPyError.

        Args:
            message: Optional error message.
            *args: Additional arguments to pass to the base
            Exception class.
        """
        self.message = message or self.__class__.__name__
        super().__init__(self.message, *args)


# Specific categories of exceptions


class ValidationError(NiveshPyError):
    """Exception raised for validation errors."""


class ResourceError(NiveshPyError):
    """Exception raised for resource-related errors."""


class DatabaseError(NiveshPyError):
    """Exception raised for database-related errors.

    This exception is intended to be raised by the niveshpy database layer
    when an unrecoverable error occurs while connecting to or interacting
    with the underlying SQLite database via SQLModel. It provides a single,
    consistent error type for callers of :mod:`niveshpy.database`, instead of
    exposing lower-level exceptions such as :class:`sqlite3.Error` or
    SQLModel-specific errors.
    """


class NetworkError(NiveshPyError):
    """Exception raised for network-related errors."""


class OperationError(NiveshPyError):
    """Exception raised for unexpected operational/runtime errors."""


# Validation errors


class InvalidInputError(ValidationError):
    """Exception raised for invalid input data."""

    def __init__(
        self, input_value: object, message: str | None = None, *args: object
    ) -> None:
        """Initialize the InvalidInputError.

        Args:
            input_value: The invalid input value.
            message: Optional custom error message.
            *args: Additional arguments to pass to the base Exception class.
        """
        if message is None:
            message = f"Invalid input: {input_value}"
        super().__init__(message, *args)
        self.input_value = input_value


class QuerySyntaxError(ValidationError):
    """Exception raised for invalid query syntax."""

    def __init__(
        self, input_value: str, message: str | None = None, *args: object
    ) -> None:
        """Initialize the QuerySyntaxError.

        Args:
            input_value: The input value with invalid syntax.
            message: Optional custom error message.
            *args: Additional arguments to pass to the base Exception class.
        """
        if message is None:
            message = f"Invalid query syntax: {input_value}"
        super().__init__(message, *args)
        self.input_value = input_value


# Resource errors


class ResourceNotFoundError(ResourceError):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource_type: str, identifier: object, *args: object) -> None:
        """Initialize the ResourceNotFoundError.

        Args:
            resource_type: The type of the resource (e.g., "User", "File").
            identifier: The identifier used to look for the resource.
            *args: Additional arguments to pass to the base Exception class.
        """
        message = f"{resource_type} with identifier '{identifier}' not found."
        super().__init__(message, *args)
        self.resource_type = resource_type
        self.identifier = identifier


class NoDataFoundError(ResourceError):
    """Exception raised when no data is found.

    This error should typically be used by data providers
    when no data is available for a given query.

    Ideally, this exception should not be propagated to end-users directly.
    Instead, this exception should be caught by an orchestration layer,
    which can then decide how to handle the absence of data
    (e.g., by trying alternative data sources or notifying the user appropriately).
    """

    def __init__(self, message: str | None = None, *args: object) -> None:
        """Initialize the NoDataFoundError.

        Args:
            message: Optional custom error message.
            *args: Additional arguments to pass to the base Exception class.
        """
        if message is None:
            message = "No data found for the given query."
        super().__init__(message, *args)


# Older exceptions - to be deprecated


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
        super().__init__(*args)  # type: ignore # This will be removed very soon.
        self.should_retry = should_retry


class InvalidSecurityError(NiveshPyError):
    """Exception raised when a security is invalid or unsupported.

    If it is not clear whether the security is invalid or just temporarily unsupported,
    consider using PriceNotFoundError instead.
    """


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

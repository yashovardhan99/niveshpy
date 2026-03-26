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

    def __str__(self):
        """Return string representation of the InvalidInputError."""
        return super().__str__() + f" (input: {self.input_value})"


class QuerySyntaxError(ValidationError):
    """Exception raised for invalid query syntax."""

    def __init__(
        self, input_value: str, cause: str, message: str | None = None, *args: object
    ) -> None:
        """Initialize the QuerySyntaxError.

        Args:
            input_value: The input value with invalid syntax.
            cause: Description of the syntax error cause.
            message: Optional custom error message.
            *args: Additional arguments to pass to the base Exception class.
        """
        if message is None:
            message = f"Syntax error in query '{input_value}': {cause}"
        super().__init__(message, *args)
        self.input_value = input_value
        self.cause = cause

    def __str__(self):
        """Return string representation of the QuerySyntaxError."""
        return super().__str__() + f" (input: {self.input_value}, cause: {self.cause})"


# Resource errors


class ResourceNotFoundError(ResourceError):
    """Exception raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str,
        identifier: object,
        message: str | None = None,
        *args: object,
    ) -> None:
        """Initialize the ResourceNotFoundError.

        Args:
            resource_type: The type of the resource (e.g., "User", "File").
            identifier: The identifier used to look for the resource.
            message: Optional custom error message.
            *args: Additional arguments to pass to the base Exception class.
        """
        if message is None:
            message = f"{resource_type} with identifier '{identifier}' not found."
        super().__init__(message, *args)
        self.resource_type = resource_type
        self.identifier = identifier

    def __str__(self):
        """Return string representation of the ResourceNotFoundError."""
        return (
            super().__str__()
            + f" (resource_type: {self.resource_type}, identifier: {self.identifier})"
        )


class AmbiguousResourceError(ResourceError):
    """Exception raised when results are ambiguous."""

    def __init__(
        self,
        resource_type: str,
        query: str,
        message: str | None = None,
        *args: object,
    ) -> None:
        """Initialize the AmbiguousResourceError.

        Args:
            resource_type: The type of the resource (e.g., "User", "File").
            query: The query used to look for the resource.
            message: Optional custom error message.
            *args: Additional arguments to pass to the base
            Exception class.
        """
        if message is None:
            message = f"Ambiguous results for {resource_type} with query '{query}'."
        super().__init__(message, *args)
        self.resource_type = resource_type
        self.query = query

    def __str__(self):
        """Return string representation of the AmbiguousResourceError."""
        return (
            super().__str__()
            + f" (resource_type: {self.resource_type}, query: {self.query})"
        )

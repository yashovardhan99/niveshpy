"""Tests for the NiveshPy exception hierarchy."""

from niveshpy.exceptions import (
    AmbiguousResourceError,
    DatabaseError,
    InvalidInputError,
    NetworkError,
    NiveshPyError,
    OperationError,
    QuerySyntaxError,
    ResourceError,
    ResourceNotFoundError,
    ValidationError,
)


class TestInheritanceHierarchy:
    """Tests verifying the exception inheritance chain."""

    def test_niveshpy_error_inherits_from_exception(self):
        """NiveshPyError should be a subclass of Exception."""
        assert isinstance(NiveshPyError(""), Exception)

    def test_validation_error_inherits(self):
        """ValidationError should inherit from NiveshPyError."""
        assert isinstance(ValidationError(""), NiveshPyError)

    def test_invalid_input_error_chain(self):
        """InvalidInputError should inherit from both ValidationError and NiveshPyError."""
        err = InvalidInputError("bad")
        assert isinstance(err, ValidationError)
        assert isinstance(err, NiveshPyError)

    def test_query_syntax_error_chain(self):
        """QuerySyntaxError should inherit from both ValidationError and NiveshPyError."""
        err = QuerySyntaxError("q", "unexpected token")
        assert isinstance(err, ValidationError)
        assert isinstance(err, NiveshPyError)

    def test_resource_error_inherits(self):
        """ResourceError should inherit from NiveshPyError."""
        assert isinstance(ResourceError(""), NiveshPyError)

    def test_resource_not_found_chain(self):
        """ResourceNotFoundError should inherit from both ResourceError and NiveshPyError."""
        err = ResourceNotFoundError("Account", 42)
        assert isinstance(err, ResourceError)
        assert isinstance(err, NiveshPyError)

    def test_ambiguous_resource_chain(self):
        """AmbiguousResourceError should inherit from both ResourceError and NiveshPyError."""
        err = AmbiguousResourceError("Security", "growth")
        assert isinstance(err, ResourceError)
        assert isinstance(err, NiveshPyError)

    def test_database_network_operation_inherit(self):
        """DatabaseError, NetworkError, and OperationError should all inherit from NiveshPyError."""
        assert isinstance(DatabaseError(""), NiveshPyError)
        assert isinstance(NetworkError(""), NiveshPyError)
        assert isinstance(OperationError(""), NiveshPyError)


class TestNiveshPyError:
    """Tests for the base NiveshPyError class."""

    def test_default_message_is_class_name(self):
        """Default message should be the class name when no message is provided."""
        err = NiveshPyError()
        assert err.message == "NiveshPyError"

    def test_custom_message(self):
        """A custom message should override the default."""
        err = NiveshPyError("custom")
        assert err.message == "custom"

    def test_message_in_args(self):
        """The message should be stored as the first element of args."""
        err = NiveshPyError("hello")
        assert err.args[0] == "hello"


class TestInvalidInputError:
    """Tests for InvalidInputError."""

    def test_default_message_format(self):
        """Default message should follow 'Invalid input: {value}' format."""
        err = InvalidInputError("abc")
        assert err.message == "Invalid input: abc"

    def test_custom_message(self):
        """A custom message should override the default format."""
        err = InvalidInputError("abc", message="bad value provided")
        assert err.message == "bad value provided"

    def test_input_value_stored(self):
        """The input_value attribute should be preserved."""
        err = InvalidInputError(42)
        assert err.input_value == 42

    def test_str_includes_input_value(self):
        """str() should include the input value."""
        err = InvalidInputError("xyz")
        assert "xyz" in str(err)


class TestQuerySyntaxError:
    """Tests for QuerySyntaxError."""

    def test_default_message_format(self):
        """Default message should follow the expected syntax error format."""
        err = QuerySyntaxError("name:", "unexpected end of query")
        assert err.message == "Syntax error in query 'name:': unexpected end of query"

    def test_custom_message(self):
        """A custom message should override the default format."""
        err = QuerySyntaxError("q", "cause", message="custom parse error")
        assert err.message == "custom parse error"

    def test_attributes_stored(self):
        """The input_value and cause attributes should be preserved."""
        err = QuerySyntaxError("foo:bar", "invalid operator")
        assert err.input_value == "foo:bar"
        assert err.cause == "invalid operator"

    def test_str_includes_input_and_cause(self):
        """str() should contain both the input value and the cause."""
        err = QuerySyntaxError("bad query", "missing colon")
        text = str(err)
        assert "bad query" in text
        assert "missing colon" in text


class TestResourceNotFoundError:
    """Tests for ResourceNotFoundError."""

    def test_default_message_format(self):
        """Default message should follow the 'not found' format."""
        err = ResourceNotFoundError("Account", 99)
        assert err.message == "Account with identifier '99' not found."

    def test_attributes_stored(self):
        """The resource_type and identifier attributes should be preserved."""
        err = ResourceNotFoundError("Security", "MF001")
        assert err.resource_type == "Security"
        assert err.identifier == "MF001"

    def test_str_includes_context(self):
        """str() should contain both resource_type and identifier."""
        err = ResourceNotFoundError("Transaction", "TX-42")
        text = str(err)
        assert "Transaction" in text
        assert "TX-42" in text


class TestAmbiguousResourceError:
    """Tests for AmbiguousResourceError."""

    def test_default_message_format(self):
        """Default message should follow the ambiguous results format."""
        err = AmbiguousResourceError("Security", "growth")
        assert err.message == "Ambiguous results for Security with query 'growth'."

    def test_attributes_stored(self):
        """The resource_type and query attributes should be preserved."""
        err = AmbiguousResourceError("Account", "savings")
        assert err.resource_type == "Account"
        assert err.query == "savings"

    def test_str_includes_context(self):
        """str() should contain both resource_type and query."""
        err = AmbiguousResourceError("Security", "hdfc")
        text = str(err)
        assert "Security" in text
        assert "hdfc" in text


class TestCategoryErrors:
    """Tests for the mid-level category error classes."""

    def test_database_error_custom_message(self):
        """DatabaseError should accept and store a custom message."""
        err = DatabaseError("connection failed")
        assert err.message == "connection failed"

    def test_network_error_custom_message(self):
        """NetworkError should accept and store a custom message."""
        err = NetworkError("timeout")
        assert err.message == "timeout"

    def test_operation_error_custom_message(self):
        """OperationError should accept and store a custom message."""
        err = OperationError("unexpected state")
        assert err.message == "unexpected state"

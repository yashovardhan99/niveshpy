"""Tests for niveshpy.models.output formatting functions."""

from decimal import Decimal

from niveshpy.models.output import format_decimal, format_percentage


class TestFormatDecimal:
    """Tests for the format_decimal function."""

    def test_none_returns_na(self) -> None:
        """Returns 'N/A' when value is None."""
        assert format_decimal(None) == "N/A"

    def test_positive_value_comma_formatted(self) -> None:
        """Formats positive decimal with comma separators."""
        assert format_decimal(Decimal("1234.56")) == "1,234.56"

    def test_zero_no_red_prefix(self) -> None:
        """Zero is not treated as negative."""
        assert format_decimal(Decimal("0")) == "0"

    def test_negative_value_red_prefix(self) -> None:
        """Negative values get a [red] prefix."""
        assert format_decimal(Decimal("-500.00")) == "[red]-500.00"

    def test_negative_value_ignore_negative(self) -> None:
        """Negative values without [red] when ignore_negative is True."""
        assert format_decimal(Decimal("-500.00"), ignore_negative=True) == "-500.00"

    def test_percentage_formatting(self) -> None:
        """Formats value as percentage when is_percentage is True."""
        assert format_decimal(Decimal("0.1845"), is_percentage=True) == "18.45%"

    def test_negative_percentage_red_prefix(self) -> None:
        """Negative percentage gets a [red] prefix."""
        assert format_decimal(Decimal("-0.05"), is_percentage=True) == "[red]-5.00%"


class TestFormatPercentage:
    """Tests for the format_percentage partial function."""

    def test_none_returns_na(self) -> None:
        """Returns 'N/A' when value is None."""
        assert format_percentage(None) == "N/A"

    def test_positive_percentage(self) -> None:
        """Formats positive value as percentage."""
        assert format_percentage(Decimal("0.25")) == "25.00%"

    def test_negative_percentage_red_prefix(self) -> None:
        """Negative percentage gets a [red] prefix."""
        assert format_percentage(Decimal("-0.10")) == "[red]-10.00%"

    def test_zero_percentage_no_red(self) -> None:
        """Zero percentage is not treated as negative."""
        assert format_percentage(Decimal("0")) == "0.00%"

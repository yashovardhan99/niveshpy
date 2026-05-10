"""Quick helpers for models."""

from decimal import Decimal


def quantize_decimal(value: Decimal, places: int = 2) -> Decimal:
    """Quantize a Decimal to a specific number of decimal places."""
    quantizer = Decimal("1").scaleb(-places)  # e.g., Decimal('0.01') for 2 places
    return value.quantize(quantizer)

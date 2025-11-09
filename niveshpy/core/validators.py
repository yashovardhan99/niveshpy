"""Validators for user input."""


def validate_date(value: str) -> bool:
    """Validate that the input string is a date in YYYY-MM-DD format."""
    from datetime import datetime

    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False

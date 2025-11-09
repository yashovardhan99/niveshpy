"""Utility functions for handling user inputs."""


def validate_date(date_str: str) -> bool:
    """Validate if the provided string is a valid date in YYYY-MM-DD format."""
    from datetime import datetime

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

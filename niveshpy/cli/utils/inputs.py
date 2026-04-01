"""Utility functions for handling user inputs."""

# Validation utilities for the CLI.


def validate_date(date_str: str) -> bool:
    """Validate if the provided string is a valid date in YYYY-MM-DD format."""
    from datetime import datetime

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# Input utilities for the CLI.


def ask_password(prompt: str = "Enter password: ") -> str:
    """Prompt the user for a password securely.

    Args:
        prompt (str): The prompt message to display.

    Returns:
        str: The password entered by the user.
    """
    from niveshpy.cli.utils.setup import _console

    return _console.input(prompt, password=True).strip()

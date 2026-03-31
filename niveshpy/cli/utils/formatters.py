"""Formatters for CLI output."""

import datetime
import decimal
import functools


def format_decimal(
    value: decimal.Decimal | None,
    is_percentage: bool = False,
    ignore_negative: bool = False,
) -> str:
    """Format decimal value as a string with appropriate formatting."""
    value_str = ""
    if value is None:
        return "N/A"
    if is_percentage:
        value_str = f"{value:.2%}"
    else:
        value_str = f"{value:,}"
    if not ignore_negative and value < 0:
        value_str = f"[red]{value_str}"
    return value_str


format_percentage = functools.partial(format_decimal, is_percentage=True)


def format_datetime(dt: datetime.datetime) -> str:
    """Format a datetime object to a relative time string.

    If the datetime is within 7 days, it shows relative time (e.g., "about 3 hours ago").
    If older than 7 days, it shows the absolute date (e.g., "on Jan 01, 2023").

    Args:
        dt (datetime.datetime): The datetime object to format.

    Returns:
        str: A human-readable relative time string.

    """
    now = datetime.datetime.now()
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"about {seconds} seconds ago"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"about {minutes} minutes ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"about {hours} hours ago"
    else:
        days = seconds // 86400
        if days < 7:
            return f"about {days} days ago"
        else:
            date = format_date(dt.date())
            return f"on {date}"


def format_date(d: datetime.date) -> str:
    """Format a date object to a string in the format 'DD MMM YYYY'."""
    return d.strftime("%d %b %Y")

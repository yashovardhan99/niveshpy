"""Utility functions for setting up the CLI application state."""

from rich.console import Console

from niveshpy.core.app import AppState

_console = Console()  # Global console instance for utility functions
_error_console = Console(stderr=True)  # Console for error messages


def initialize_app_state(state: AppState) -> None:
    """Initialize the application state for CLI operations.

    This function sets up the application state by determining interactivity,
    color settings, and initializing logging.

    Args:
        state (AppState): The application state object to initialize.
    """
    from niveshpy.cli.utils import logging

    if not state.no_input:
        # If no_input is not set, determine interactivity from console
        state.no_input = not _console.is_interactive

    if state.no_color:
        _console.no_color = True
        _error_console.no_color = True

    logging.setup(state.debug, _error_console)  # Initialize logging with debug flag

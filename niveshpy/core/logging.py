"""Logging setup for niveshpy.

Logging Strategy
================

NiveshPy uses a central ``niveshpy`` logger with two handlers configured in
``cli/utils/logging.py``: a RotatingFileHandler (1 MB, 3 backups) and a
RichHandler for console output.  The ``--debug`` flag toggles between normal
mode (file=INFO, console=WARNING) and debug mode (file=DEBUG, console=INFO).

Level Guidelines:
    CRITICAL: Application cannot start — database corruption, missing critical
        configuration, or unrecoverable environment errors.
    ERROR: An operation failed and requires user action — XIRR computation
        failure, unresolvable duplicate records, or invalid user input that
        prevents completing a command.
    WARNING: Unexpected but recoverable situations — missing prices for a
        security, provider timeout with fallback, partial parse results.
    INFO: Significant operations completing successfully — external HTTP calls,
        file parsing results, database initialisation, service-level outcomes,
        plugin registration.
    DEBUG: Diagnostic detail useful during development — function parameters,
        intermediate computation results, query-parser tokens, feature-flag
        values.

Principles:
    * User-facing output goes through Rich helpers (``display_success``,
      ``display_error``); logging is strictly for diagnostics.
    * Log at service-method boundaries, not inside tight loops.
    * Log all external I/O unconditionally at INFO (HTTP calls, file parsing,
      database initialisation).
    * Log recovered errors at WARNING with the original exception context.
    * Models should never log; keep them pure data containers.
    * Use ``%s``-style formatting (``logger.info("Fetched %s prices", count)``)
      so formatting is deferred until the message is actually emitted.
"""

import logging
import logging.config
import logging.handlers

logger = logging.getLogger("niveshpy")


def setup(*handlers: logging.Handler) -> None:
    """Set up logging configuration."""
    logger.setLevel(logging.DEBUG)
    for handler in handlers:
        logger.addHandler(handler)
    logger.debug("Logging initialized with handlers: %s.", handlers)

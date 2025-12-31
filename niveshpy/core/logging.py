"""Logging setup for niveshpy."""

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

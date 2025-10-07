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


def update(*levels: int) -> None:
    """Update logging level."""
    for level, handler in zip(levels, logger.handlers, strict=False):
        handler.setLevel(level)
        logger.debug(
            "%s Logging level updated to %s.",
            handler.__class__.__name__,
            logging.getLevelName(level),
        )

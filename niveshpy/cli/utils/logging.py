"""Set up logging for Niveshpy CLI."""

from logging import Formatter
from logging.handlers import RotatingFileHandler
import platformdirs
from rich.logging import RichHandler
from logging import DEBUG, INFO, WARNING

from niveshpy.core import logging


def setup(debug: bool) -> None:
    """Set up logging configuration for CLI."""
    log_path = (
        platformdirs.user_log_path("niveshpy", ensure_exists=True) / "niveshpy.log"
    ).resolve()
    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    FORMAT = "%(asctime)s :: %(name)-12s :: %(levelname)-8s :: %(message)s"
    file_handler.setFormatter(Formatter(fmt=FORMAT))
    file_handler.setLevel(DEBUG if debug else INFO)

    console_handler = RichHandler(
        level=INFO if debug else WARNING,
        show_path=False,
        log_time_format="[%Y-%m-%d %H:%M:%S]",
    )

    logging.setup(file_handler, console_handler)


def update(debug: bool) -> None:
    """Update logging level for CLI."""
    logging.update(
        DEBUG if debug else INFO,
        INFO if debug else WARNING,
    )

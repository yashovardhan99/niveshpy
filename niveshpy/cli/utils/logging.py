"""Set up logging for Niveshpy CLI."""

from logging import DEBUG, INFO, WARNING, Filter, Formatter
from logging.handlers import RotatingFileHandler

import platformdirs
from rich.console import Console
from rich.logging import RichHandler

from niveshpy.core import logging


class TracebackInfoFilter(Filter):
    """Filter to control traceback information in logs."""

    def filter(self, record):
        """Filter out exception info from log records."""
        record._exc_info_hidden, record.exc_info = record.exc_info, None
        record.exc_text = None
        return True


def setup(debug: bool, console: Console) -> None:
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
        console=console,
        show_path=False,
        log_time_format="[%Y-%m-%d %H:%M:%S]",
        show_time=debug,
        rich_tracebacks=True,
    )
    if not debug:
        console_handler.addFilter(TracebackInfoFilter())

    logging.setup(file_handler, console_handler)

    if debug:
        logging.logger.info("Logging to file: %s", log_path.as_posix())

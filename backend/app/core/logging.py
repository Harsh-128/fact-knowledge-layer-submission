import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """
    Configure application-wide logging.

    Logs are written to stdout so they are visible both locally
    and inside Docker/Celery containers.
    """

    log_level = logging.DEBUG if settings.debug else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
        force=True,
    )

    # Keep noisy third-party libraries under control.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the requested module."""
    return logging.getLogger(name)
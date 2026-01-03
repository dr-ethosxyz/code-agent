"""
Logging configuration for Matter PR Reviewer Agent.
"""

import sys
from typing import Optional

from loguru import logger

from src.config import settings


def configure_logging() -> None:
    """Configure colorful logging for the application."""

    logger.remove()

    log_level = "DEBUG" if settings.debug else "INFO"

    if settings.environment == "development":
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<blue>{name}</blue>:<blue>{function}</blue>:<blue>{line}</blue> - "
                "<level>{message}</level>"
            ),
            level=log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        logger.add(
            sys.stderr,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
                "{name}:{function}:{line} - {message}"
            ),
            level=log_level,
            serialize=True,
        )


configure_logging()


def get_logger(name: Optional[str] = None):
    """Get a logger instance with optional name binding."""
    if name:
        return logger.bind(logger_name=name)
    return logger

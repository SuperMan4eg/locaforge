"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "locaforge"


def configure_logging(data_root: Path) -> Path:
    """Configure the application logger and return the active log path."""
    log_directory = data_root / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "locaforge.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in tuple(logger.handlers):
        if getattr(handler, "_locaforge_managed", False):
            logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(threadName)s: %(message)s"
        )
    )
    handler._locaforge_managed = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    return log_path

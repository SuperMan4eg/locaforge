"""Global exception handling for the desktop application."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import QMessageBox

from locaforge.app.logging_config import LOGGER_NAME

type ExceptionHook = Callable[[type[BaseException], BaseException, TracebackType | None], None]


def build_exception_hook(
    log_path: Path,
    notifier: Callable[[str], None] | None = None,
    fallback: ExceptionHook | None = None,
) -> ExceptionHook:
    """Create an exception hook that logs failures and informs the user."""
    fallback_hook = fallback or sys.__excepthook__

    def handle_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            fallback_hook(exception_type, exception, traceback)
            return
        logging.getLogger(LOGGER_NAME).critical(
            "Unhandled application exception",
            exc_info=(exception_type, exception, traceback),
        )
        if notifier is not None:
            notifier(str(log_path))

    return handle_exception


def install_exception_handler(log_path: Path) -> None:
    """Install the production exception hook with a Qt error dialog."""

    def notify_user(path: str) -> None:
        QMessageBox.critical(
            None,
            "Unexpected LocaForge error",
            f"An unexpected error occurred. Details were written to:\n{path}",
        )

    sys.excepthook = build_exception_hook(log_path, notify_user)

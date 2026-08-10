"""Global exception handling for the desktop application."""

from __future__ import annotations

import logging
import secrets
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import QMessageBox

from locaforge.app.logging_config import LOGGER_NAME

type ExceptionHook = Callable[[type[BaseException], BaseException, TracebackType | None], None]
type IncidentNotifier = Callable[[str], None]
type IncidentIdFactory = Callable[[], str]

_incident_lock = threading.Lock()
_last_incident_id: str | None = None


def get_last_incident_id() -> str | None:
    with _incident_lock:
        return _last_incident_id


def _record_incident(incident_id: str) -> None:
    global _last_incident_id
    with _incident_lock:
        _last_incident_id = incident_id


def _new_incident_id() -> str:
    return secrets.token_hex(4).upper()


def build_exception_hook(
    log_path: Path,
    notifier: IncidentNotifier | None = None,
    fallback: ExceptionHook | None = None,
    incident_id_factory: IncidentIdFactory = _new_incident_id,
    incident_sink: IncidentNotifier = _record_incident,
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
        incident_id = incident_id_factory()
        incident_sink(incident_id)
        logging.getLogger(LOGGER_NAME).critical(
            "Unhandled application exception [incident_id=%s]",
            incident_id,
            exc_info=(exception_type, exception, traceback),
        )
        if notifier is not None:
            notifier(incident_id)

    return handle_exception


def install_exception_handler(log_path: Path, *, show_dialog: bool = True) -> None:
    """Install the production exception hook with a Qt error dialog."""

    def notify_user(incident_id: str) -> None:
        QMessageBox.critical(
            None,
            "Unexpected LocaForge error",
            "An unexpected error occurred. Details were saved in the local application log.\n\n"
            f"Incident ID: {incident_id}\n\n"
            "Use Copy diagnostics in the Logs panel when contacting support.",
        )

    sys.excepthook = build_exception_hook(log_path, notify_user if show_dialog else None)

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType

from locaforge.app.exception_handler import build_exception_hook
from locaforge.app.logging_config import LOGGER_NAME, configure_logging


def test_configure_logging_writes_utf8_log(tmp_path: Path) -> None:
    log_path = configure_logging(tmp_path)

    logging.getLogger(LOGGER_NAME).info("Запуск")
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()

    assert log_path.read_text(encoding="utf-8").endswith("Запуск\n")


def test_exception_hook_logs_traceback_and_notifies(tmp_path: Path) -> None:
    log_path = configure_logging(tmp_path)
    notifications: list[str] = []
    hook = build_exception_hook(log_path, notifications.append)

    try:
        raise ValueError("broken project")
    except ValueError as error:
        hook(type(error), error, error.__traceback__)
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()

    log_contents = log_path.read_text(encoding="utf-8")
    assert "Unhandled application exception" in log_contents
    assert "ValueError: broken project" in log_contents
    assert notifications == [str(log_path)]


def test_exception_hook_delegates_keyboard_interrupt(tmp_path: Path) -> None:
    calls: list[type[BaseException]] = []

    def fallback(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        calls.append(exception_type)

    hook = build_exception_hook(tmp_path / "locaforge.log", fallback=fallback)
    error = KeyboardInterrupt()

    hook(type(error), error, error.__traceback__)

    assert calls == [KeyboardInterrupt]

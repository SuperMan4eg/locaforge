"""Thread-safe bridge from application logging to a Qt log viewer."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class _QtLogHandler(logging.Handler):
    def __init__(self, receiver: LogViewerController) -> None:
        super().__init__()
        self._receiver = receiver

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._receiver.message_logged.emit(self.format(record))
        except Exception:
            self.handleError(record)


class LogViewerController(QObject):
    """Attaches a logging handler that forwards formatted records to Qt."""

    message_logged = Signal(str)

    def __init__(
        self,
        logger_name: str = "locaforge",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._logger = logging.getLogger(logger_name)
        self._handler = _QtLogHandler(self)
        self._handler.setLevel(logging.INFO)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        )
        self._attached = False

    def attach(self) -> None:
        if self._attached:
            return
        self._logger.addHandler(self._handler)
        self._attached = True

    def detach(self) -> None:
        if not self._attached:
            return
        self._logger.removeHandler(self._handler)
        self._attached = False

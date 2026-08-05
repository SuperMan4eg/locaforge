"""Background worker for translation-memory suggestions."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from locaforge.domain.translation_memory import TranslationMemoryMatch

logger = logging.getLogger(__name__)

type FindMatchesOperation = Callable[[], tuple[TranslationMemoryMatch, ...]]


class TranslationMemoryWorker(QThread):
    """Loads suggestions without blocking table-row selection."""

    succeeded = Signal(int, object)
    failed = Signal(int, str)

    def __init__(
        self,
        request_id: int,
        operation: FindMatchesOperation,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._request_id = request_id
        self._operation = operation

    def run(self) -> None:
        try:
            matches = self._operation()
        except Exception as error:
            logger.exception("Translation memory lookup failed")
            self.failed.emit(self._request_id, str(error))
            return
        self.succeeded.emit(self._request_id, matches)

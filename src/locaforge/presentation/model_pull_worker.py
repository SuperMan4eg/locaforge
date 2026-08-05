"""Background worker for downloading an Ollama model."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

logger = logging.getLogger(__name__)


class ModelPullWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self, model: str, operation: Callable[[], None], parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._operation = operation

    def run(self) -> None:
        try:
            self._operation()
        except Exception as error:
            logger.exception("Ollama model installation failed")
            self.failed.emit(str(error))
            return
        self.succeeded.emit(self._model)

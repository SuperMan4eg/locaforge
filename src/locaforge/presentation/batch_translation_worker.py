"""Background Qt worker for batch translation."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from locaforge.application.dto.translation import BatchResult

logger = logging.getLogger(__name__)

type ProgressCallback = Callable[[int, int], None]
type CancellationCheck = Callable[[], bool]
type BatchOperation = Callable[[ProgressCallback, CancellationCheck], BatchResult]


class BatchTranslationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(
        self,
        operation: BatchOperation,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._operation = operation

    def run(self) -> None:
        try:
            result = self._operation(self._report_progress, self.isInterruptionRequested)
        except Exception as error:
            logger.exception("Batch translation worker failed")
            self.failed.emit(str(error))
            return
        self.succeeded.emit(result)

    def _report_progress(self, completed: int, total: int) -> None:
        self.progress.emit(completed, total)

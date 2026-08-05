"""Background worker for local AI review."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from locaforge.application.dto.review import ReviewBatchResult

logger = logging.getLogger(__name__)

type ProgressCallback = Callable[[int, int], None]
type CancellationCheck = Callable[[], bool]
type ReviewOperation = Callable[[ProgressCallback, CancellationCheck], ReviewBatchResult]


class ReviewWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, operation: ReviewOperation, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._operation = operation

    def run(self) -> None:
        try:
            result = self._operation(self._report_progress, self.isInterruptionRequested)
            self.succeeded.emit(result)
        except Exception as error:
            logger.exception("AI review worker failed")
            self.failed.emit(str(error))

    def _report_progress(self, completed: int, total: int) -> None:
        self.progress.emit(completed, total)

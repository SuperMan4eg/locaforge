"""Run project validation without blocking the Qt event loop."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from locaforge.application.dto.validation import ProjectValidationResult

logger = logging.getLogger(__name__)

type ValidationOperation = Callable[[], ProjectValidationResult]


class ValidationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self, operation: ValidationOperation, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._operation = operation

    def run(self) -> None:
        try:
            self.succeeded.emit(self._operation())
        except Exception as error:
            logger.exception("Validation worker failed")
            self.failed.emit(str(error))

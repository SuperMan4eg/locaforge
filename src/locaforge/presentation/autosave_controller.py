"""Debounced autosave orchestration for the desktop UI."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Signal

logger = logging.getLogger(__name__)


class _AutosaveWorker(QThread):
    saved = Signal()
    failed = Signal(str)

    def __init__(self, save_action: Callable[[], object], parent: QObject) -> None:
        super().__init__(parent)
        self._save_action = save_action

    def run(self) -> None:
        try:
            self._save_action()
        except Exception as error:
            logger.exception("Project autosave failed")
            self.failed.emit(str(error))
            return
        self.saved.emit()


class AutosaveController(QObject):
    saved = Signal()
    failed = Signal(str)

    def __init__(
        self,
        save_action: Callable[[], object],
        delay_ms: int = 2000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if delay_ms < 1:
            raise ValueError("Autosave delay must be positive")
        self._save_action = save_action
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._perform_save)
        self._worker: _AutosaveWorker | None = None
        self._reschedule_after_save = False

    @property
    def is_pending(self) -> bool:
        return self._timer.isActive() or self._worker is not None

    def schedule(self) -> None:
        if self._worker is not None:
            self._reschedule_after_save = True
            return
        self._timer.start()

    def cancel(self) -> None:
        self._timer.stop()
        self._reschedule_after_save = False

    def flush(self) -> None:
        self._timer.stop()
        if self._worker is not None:
            self._reschedule_after_save = True
            return
        try:
            self._save_action()
        except Exception as error:
            logger.exception("Project autosave failed")
            self.failed.emit(str(error))
            return
        self.saved.emit()

    def wait_for_completion(self) -> None:
        self._timer.stop()
        if self._worker is not None:
            self._worker.wait()

    def _perform_save(self) -> None:
        if self._worker is not None:
            self._reschedule_after_save = True
            return
        worker = _AutosaveWorker(self._save_action, self)
        worker.saved.connect(self.saved)
        worker.failed.connect(self.failed)
        worker.finished.connect(self._autosave_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _autosave_finished(self) -> None:
        self._worker = None
        if self._reschedule_after_save:
            self._reschedule_after_save = False
            self.schedule()

"""Background worker for project-profile generation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from locaforge.domain.project_profile import ProjectProfile


class ProfileGenerationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        generate: Callable[[], ProjectProfile],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._generate = generate

    def run(self) -> None:
        try:
            self.succeeded.emit(self._generate())
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))

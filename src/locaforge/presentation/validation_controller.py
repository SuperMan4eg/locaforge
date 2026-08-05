"""Project validation workflow orchestration for the desktop UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject

from locaforge.application.dto.validation import ProjectValidationResult
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.validation_worker import ValidationWorker

type SetBusy = Callable[[bool, bool], None]
type RefreshProject = Callable[[bool], None]
type ShowStatus = Callable[[str, int], None]
type ShowError = Callable[[str, str], None]


class ValidationController(QObject):
    """Owns the non-cancellable background project validation worker."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        set_busy: SetBusy,
        refresh_project: RefreshProject,
        sync_autosave: Callable[[], None],
        disable_cancel: Callable[[], None],
        show_status: ShowStatus,
        show_error: ShowError,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._set_busy = set_busy
        self._refresh_project = refresh_project
        self._sync_autosave = sync_autosave
        self._disable_cancel = disable_cancel
        self._show_status = show_status
        self._show_error = show_error
        self._worker: ValidationWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self) -> bool:
        if self.is_running:
            return False
        worker = ValidationWorker(self._workspace.validate_project, self)
        worker.succeeded.connect(self._validation_succeeded)
        worker.failed.connect(self._validation_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self._set_busy(True, True)
        self._disable_cancel()
        self._show_status("Validating project...", 0)
        worker.start()
        return True

    def _validation_succeeded(self, result_object: object) -> None:
        self._worker = None
        self._set_busy(False, False)
        if not isinstance(result_object, ProjectValidationResult):
            self._show_error("Validation", "Worker returned an invalid result")
            return
        self._refresh_project(False)
        self._sync_autosave()
        self._show_status(
            "Project validation completed: "
            f"{result_object.entries_checked} checked, "
            f"{result_object.entries_with_issues} with issues",
            5000,
        )

    def _validation_failed(self, message: str) -> None:
        self._worker = None
        self._set_busy(False, True)
        self._show_error("Validation failed", message)

"""AI review workflow orchestration for the desktop UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject

from locaforge.application.dto.review import ReviewBatchResult
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.review_worker import ReviewWorker

type EnsureModel = Callable[[str, bool], bool]
type SetBusy = Callable[[bool, bool], None]
type RefreshProject = Callable[[bool], None]
type ShowStatus = Callable[[str, int], None]
type ShowError = Callable[[str, str], None]
type ShowProgress = Callable[[int, int], None]


class ReviewController(QObject):
    """Owns the background worker and completion lifecycle for AI review."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        ensure_model: EnsureModel,
        set_busy: SetBusy,
        refresh_project: RefreshProject,
        sync_autosave: Callable[[], None],
        show_status: ShowStatus,
        show_error: ShowError,
        show_progress: ShowProgress,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._ensure_model = ensure_model
        self._set_busy = set_busy
        self._refresh_project = refresh_project
        self._sync_autosave = sync_autosave
        self._show_status = show_status
        self._show_error = show_error
        self._show_progress = show_progress
        self._worker: ReviewWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self, entry_ids: tuple[str, ...]) -> bool:
        if not entry_ids or self.is_running:
            return False
        review_model = self._workspace.resolve_model_settings().effective_review_model
        if not self._ensure_model(review_model, True):
            return False
        worker = ReviewWorker(
            lambda progress, is_cancelled: self._workspace.review_entries(
                entry_ids,
                progress_callback=progress,
                cancellation_check=is_cancelled,
            ),
            self,
        )
        worker.succeeded.connect(self._review_succeeded)
        worker.failed.connect(self._review_failed)
        worker.progress.connect(self._review_progress)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self._set_busy(True, True)
        self._show_status(f"Reviewing {len(entry_ids)} entries...", 0)
        worker.start()
        return True

    def cancel(self) -> bool:
        if not self.is_running or self._worker is None:
            return False
        self._worker.requestInterruption()
        return True

    def _review_succeeded(self, result_object: object) -> None:
        self._worker = None
        self._set_busy(False, False)
        if not isinstance(result_object, ReviewBatchResult):
            self._show_error("AI review", "Worker returned an invalid result")
            return
        self._refresh_project(False)
        if result_object.cancelled:
            message = f"AI review cancelled after {result_object.reviewed_entries} entries"
        else:
            message = f"AI review completed: {result_object.issue_count} issue(s)"
        self._show_status(message, 5000)
        self._sync_autosave()

    def _review_progress(self, completed: int, total: int) -> None:
        self._show_progress(completed, total)

    def _review_failed(self, message: str) -> None:
        self._worker = None
        self._set_busy(False, True)
        self._show_error("AI review failed", message)

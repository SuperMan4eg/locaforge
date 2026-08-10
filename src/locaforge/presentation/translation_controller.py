"""Batch translation workflow orchestration for the desktop UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject

from locaforge.application.dto.translation import BatchResult
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.batch_translation_worker import BatchTranslationWorker

type EnsureModel = Callable[[str], bool]
type SetBusy = Callable[[bool, bool], None]
type RefreshProject = Callable[[bool], None]
type ShowMessage = Callable[[str, str], None]
type ShowStatus = Callable[[str, int], None]
type ShowProgress = Callable[[int, int], None]


class TranslationController(QObject):
    """Owns the background worker and completion lifecycle for translation."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        ensure_model: EnsureModel,
        set_busy: SetBusy,
        refresh_project: RefreshProject,
        sync_autosave: Callable[[], None],
        show_status: ShowStatus,
        show_error: ShowMessage,
        show_warning: ShowMessage,
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
        self._show_warning = show_warning
        self._show_progress = show_progress
        self._worker: BatchTranslationWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self, entry_ids: tuple[str, ...]) -> bool:
        if not entry_ids or self.is_running:
            return False
        model = self._workspace.resolve_model_settings().model
        if not self._ensure_model(model):
            return False
        worker = BatchTranslationWorker(
            lambda progress, is_cancelled: self._workspace.translate_entries(
                entry_ids,
                progress_callback=progress,
                cancellation_check=is_cancelled,
            ),
            self,
        )
        worker.succeeded.connect(self._translation_succeeded)
        worker.failed.connect(self._translation_failed)
        worker.progress.connect(self._translation_progress)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self._set_busy(True, True)
        worker.start()
        return True

    def cancel(self) -> bool:
        if not self.is_running or self._worker is None:
            return False
        self._worker.requestInterruption()
        return True

    def _translation_succeeded(self, result_object: object) -> None:
        self._worker = None
        self._set_busy(False, False)
        if not isinstance(result_object, BatchResult):
            self._show_error("Batch translation", "Worker returned an invalid result")
            return
        self._refresh_project(False)
        translated_count = len(result_object.translated_entry_ids)
        if result_object.cancelled:
            status = f"Translation cancelled after {translated_count} completed entries"
        else:
            status = f"Translated {translated_count} entries"
        self._show_status(status, 5000)
        if result_object.errors:
            self._show_warning(
                "Batch translation completed with errors",
                "\n".join(result_object.errors),
            )
        self._sync_autosave()

    def _translation_progress(self, completed: int, total: int) -> None:
        self._show_progress(completed, total)

    def _translation_failed(self, message: str) -> None:
        self._worker = None
        self._set_busy(False, True)
        self._show_error("Batch translation failed", message)

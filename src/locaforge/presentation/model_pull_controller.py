"""Ollama model download orchestration for the desktop UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.model_pull_worker import ModelPullWorker

type SetBusy = Callable[[bool, bool], None]
type ShowStatus = Callable[[str, int], None]
type ShowError = Callable[[str, str], None]


class ModelPullController(QObject):
    """Owns the background Ollama model download lifecycle."""

    started = Signal(str)
    completed = Signal(str, bool, str)

    def __init__(
        self,
        workspace: ProjectWorkspace,
        set_busy: SetBusy,
        prepare_progress: Callable[[], None],
        show_status: ShowStatus,
        show_error: ShowError,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._set_busy = set_busy
        self._prepare_progress = prepare_progress
        self._show_status = show_status
        self._show_error = show_error
        self._worker: ModelPullWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(
        self,
        model: str,
        pull_operation: Callable[[], None] | None = None,
    ) -> bool:
        normalized_model = model.strip()
        if not normalized_model or self.is_running:
            return False
        worker = ModelPullWorker(
            normalized_model,
            pull_operation or (lambda: self._workspace.pull_model(normalized_model)),
            self,
        )
        worker.succeeded.connect(self._model_pull_succeeded)
        worker.failed.connect(self._model_pull_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self._set_busy(True, True)
        self._prepare_progress()
        self._show_status(f"Downloading Ollama model {normalized_model}...", 0)
        self.started.emit(normalized_model)
        worker.start()
        return True

    def _model_pull_succeeded(self, model: str) -> None:
        self._worker = None
        self._set_busy(False, True)
        self._show_status(f"Ollama model {model} installed", 5000)
        self.completed.emit(model, True, "")

    def _model_pull_failed(self, message: str) -> None:
        self._worker = None
        self._set_busy(False, True)
        self._show_error("Ollama model installation failed", message)
        self.completed.emit("", False, message)

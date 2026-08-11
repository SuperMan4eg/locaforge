"""Unsaved-change confirmation and safe window shutdown orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum

from locaforge.application.project_workspace import ProjectWorkspace

logger = logging.getLogger(__name__)


class UnsavedChangesDecision(StrEnum):
    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"


class WindowCloseController:
    """Guards window shutdown and performs ordered cleanup."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        translation_running: Callable[[], bool],
        review_running: Callable[[], bool],
        validation_running: Callable[[], bool],
        model_pull_running: Callable[[], bool],
        ask_unsaved_changes: Callable[[], UnsavedChangesDecision],
        cancel_autosave: Callable[[], None],
        wait_for_autosave: Callable[[], None],
        persist_layout: Callable[[], None],
        detach_log_viewer: Callable[[], None],
        show_warning: Callable[[str, str], None],
        show_save_error: Callable[[str], None],
    ) -> None:
        self._workspace = workspace
        self._translation_running = translation_running
        self._review_running = review_running
        self._validation_running = validation_running
        self._model_pull_running = model_pull_running
        self._ask_unsaved_changes = ask_unsaved_changes
        self._cancel_autosave = cancel_autosave
        self._wait_for_autosave = wait_for_autosave
        self._persist_layout = persist_layout
        self._detach_log_viewer = detach_log_viewer
        self._show_warning = show_warning
        self._show_save_error = show_save_error

    def confirm_unsaved_changes(self) -> bool:
        if not self._workspace.has_project or not self._workspace.project.dirty:
            return True
        decision = self._ask_unsaved_changes()
        if decision is UnsavedChangesDecision.CANCEL:
            return False
        if decision is UnsavedChangesDecision.DISCARD:
            self._cancel_autosave()
            return True
        try:
            self._workspace.save()
        except Exception as error:
            logger.exception("Project save during close failed")
            self._show_save_error(str(error))
            return False
        self._cancel_autosave()
        return True

    def request_close(self) -> bool:
        blockers = (
            (
                self._translation_running,
                "Translation in progress",
                "Wait for the current translation request to finish before closing LocaForge.",
            ),
            (
                self._review_running,
                "AI review in progress",
                "Wait for the current AI review request to finish before closing LocaForge.",
            ),
            (
                self._validation_running,
                "Validation in progress",
                "Wait for project validation to finish before closing LocaForge.",
            ),
            (
                self._model_pull_running,
                "Model download in progress",
                "Wait for the Ollama model download to finish before closing LocaForge.",
            ),
        )
        for is_running, title, message in blockers:
            if is_running():
                self._show_warning(title, message)
                return False
        if not self.confirm_unsaved_changes():
            return False
        self._wait_for_autosave()
        self._persist_layout()
        self._detach_log_viewer()
        return True

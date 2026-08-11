"""Autosave eligibility and result handling."""

from __future__ import annotations

from collections.abc import Callable

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.application_settings import ApplicationSettings


class AutosavePolicyController:
    """Keeps autosave scheduling consistent with project and application state."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        application_settings: Callable[[], ApplicationSettings],
        schedule: Callable[[], None],
        cancel: Callable[[], None],
        refresh_project: Callable[[], None],
        show_status: Callable[[str, int], None],
        show_failure: Callable[[str], None],
    ) -> None:
        self._workspace = workspace
        self._application_settings = application_settings
        self._schedule = schedule
        self._cancel = cancel
        self._refresh_project = refresh_project
        self._show_status = show_status
        self._show_failure = show_failure

    def sync(self) -> None:
        settings = self._application_settings()
        if (
            settings.autosave_enabled
            and self._workspace.has_project
            and self._workspace.session.container_path is not None
            and self._workspace.project.dirty
        ):
            self._schedule()
        else:
            self._cancel()

    def succeeded(self) -> None:
        self._workspace.refresh_after_autosave()
        self._refresh_project()
        self._show_status("Project autosaved", 3000)

    def failed(self, message: str) -> None:
        self._show_failure(message)

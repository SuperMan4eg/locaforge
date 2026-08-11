"""Open, recover, and save project orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.project_io_controller import ProjectIoController

logger = logging.getLogger(__name__)


class ProjectLifecycleController:
    """Coordinates project persistence workflows outside Qt widgets."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        project_io: ProjectIoController,
        choose_open_path: Callable[[], Path | None],
        choose_save_path: Callable[[], Path | None],
        confirm_unsaved_changes: Callable[[], bool],
        confirm_recovery: Callable[[Exception, Path], bool],
        show_open_error: Callable[[str], None],
        project_opened: Callable[[], None],
    ) -> None:
        self._workspace = workspace
        self._project_io = project_io
        self._choose_open_path = choose_open_path
        self._choose_save_path = choose_save_path
        self._confirm_unsaved_changes = confirm_unsaved_changes
        self._confirm_recovery = confirm_recovery
        self._show_open_error = show_open_error
        self._project_opened = project_opened

    def open_project(self) -> None:
        path = self._choose_open_path()
        if path is None or not self._confirm_unsaved_changes():
            return
        try:
            self._workspace.open(path)
        except Exception as error:
            logger.exception("Project open failed")
            backup_path = self._workspace.backup_path(path)
            if not backup_path.is_file():
                self._show_open_error(str(error))
                return
            if self._confirm_recovery(error, backup_path):
                self._project_io.open_backup(path)
            return
        self._project_opened()

    def save_project(self) -> None:
        if self._workspace.has_project and self._workspace.session.container_path is None:
            self.save_project_as()
            return
        self._project_io.save()

    def save_project_as(self) -> None:
        if not self._workspace.has_project:
            return
        destination = self._choose_save_path()
        if destination is not None:
            self._project_io.save(destination)

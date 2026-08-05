"""Recent-project menu orchestration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMenu

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.recent_projects import RecentProjectsStore

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]
type ShowInfo = Callable[[str, str], None]


class RecentProjectsController(QObject):
    """Builds the recent-project menu and opens remembered containers."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        store: RecentProjectsStore,
        menu: QMenu,
        run_action: ActionRunner,
        confirm_unsaved: Callable[[], bool],
        show_info: ShowInfo,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._store = store
        self._menu = menu
        self._run_action = run_action
        self._confirm_unsaved = confirm_unsaved
        self._show_info = show_info

    def remember_current(self) -> None:
        container_path = self._workspace.session.container_path
        if container_path is None:
            return
        self._store.add(container_path)
        self.refresh()

    def refresh(self) -> None:
        self._menu.clear()
        paths = self._store.list_paths()
        if not paths:
            empty_action = self._menu.addAction("No recent projects")
            empty_action.setEnabled(False)
            return
        for project_path in paths:
            action = self._menu.addAction(
                f"{project_path.name} — {project_path.parent}"
            )
            action.triggered.connect(
                lambda checked=False, path=project_path: self.open(path)
            )
        self._menu.addSeparator()
        clear_action = self._menu.addAction("Clear recent projects")
        clear_action.triggered.connect(self.clear)

    def open(self, project_path: Path) -> bool:
        if not project_path.is_file():
            self._store.remove(project_path)
            self.refresh()
            self._show_info(
                "Recent project unavailable",
                f"The project file no longer exists:\n{project_path}",
            )
            return False
        if not self._confirm_unsaved():
            return False
        succeeded = self._run_action(
            lambda: self._workspace.open(project_path), "Project opened"
        )
        if succeeded:
            self.remember_current()
        return succeeded

    def clear(self) -> None:
        self._store.clear()
        self.refresh()

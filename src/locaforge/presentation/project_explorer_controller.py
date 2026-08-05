"""Project overview dock presentation."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QListWidget

from locaforge.application.project_workspace import ProjectWorkspace


class ProjectExplorerController(QObject):
    """Renders project metadata and translation statistics."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        view: QListWidget,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._view = view

    def refresh(self) -> None:
        self._view.clear()
        if not self._workspace.has_project:
            self._view.addItem("No project open")
            return
        project = self._workspace.project
        statistics = self._workspace.project_statistics()
        self._view.addItem(project.name)
        self._view.addItem(f"{project.source_language} -> {project.target_language}")
        self._view.addItem(
            f"Progress: {statistics.completion_percent}% "
            f"({statistics.translated_entries}/{statistics.total_entries})"
        )
        self._view.addItem(f"Untranslated: {statistics.untranslated_entries}")
        self._view.addItem(f"Needs review: {statistics.needs_review_entries}")
        self._view.addItem(f"Approved: {statistics.approved_entries}")
        self._view.addItem(f"Errors: {statistics.error_entries}")
        self._view.addItem(f"Validation issues: {statistics.entries_with_issues}")
        self._view.addItem(f"Locked: {statistics.locked_entries}")

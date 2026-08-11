"""Destructive project-document operation orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject

from locaforge.application.dto.project import DocumentRefreshPreview
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.project_explorer_controller import ProjectExplorerController

logger = logging.getLogger(__name__)

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


class ProjectDocumentOperationsController(QObject):
    """Coordinate remove and source-refresh flows independently of dialog widgets."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        explorer: ProjectExplorerController,
        *,
        run_action: ActionRunner,
        confirm_remove: Callable[[int, int], bool],
        confirm_refresh: Callable[[DocumentRefreshPreview], bool],
        show_refresh_error: Callable[[str], None],
        clear_selection: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._explorer = explorer
        self._run_action = run_action
        self._confirm_remove = confirm_remove
        self._confirm_refresh = confirm_refresh
        self._show_refresh_error = show_refresh_error
        self._clear_selection = clear_selection

    def remove_selected(self) -> None:
        document_ids = tuple(self._explorer.selected_document_ids())
        if not document_ids:
            return
        entry_count = sum(
            entry.document_id in document_ids
            for entry in self._workspace.project.entries
        )
        if not self._confirm_remove(len(document_ids), entry_count):
            return
        if self._run_action(
            lambda: self._workspace.remove_documents(document_ids),
            f"{len(document_ids)} project files removed",
        ):
            self._clear_selection()

    def refresh_selected(self) -> None:
        document_ids = tuple(self._explorer.selected_document_ids())
        if not document_ids:
            return
        try:
            preview = self._workspace.preview_document_refresh(document_ids)
        except Exception as error:
            logger.exception("Document refresh preview failed")
            self._show_refresh_error(str(error))
            return
        if not self._confirm_refresh(preview):
            return
        self._run_action(
            lambda: self._workspace.refresh_documents(document_ids),
            f"{preview.document_count} source files refreshed",
        )

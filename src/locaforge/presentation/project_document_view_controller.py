"""Read-only project document selection and details coordination."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QPoint
from PySide6.QtWidgets import QMenu

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import EntryStatus
from locaforge.presentation.project_explorer_controller import ProjectExplorerController
from locaforge.presentation.project_workspace_widgets import ProjectWorkspaceWidgets


class ProjectDocumentViewController(QObject):
    """Coordinate document selection, filtering, counts and detail rendering."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        explorer: ProjectExplorerController,
        widgets: ProjectWorkspaceWidgets,
        *,
        set_document_filter: Callable[[frozenset[str]], None],
        is_busy: Callable[[], bool],
        show_translations: Callable[[], None],
        open_source_path: Callable[[Path], None] | None = None,
        refresh_selected: Callable[[], None] | None = None,
        export_selected: Callable[[], None] | None = None,
        remove_selected: Callable[[], None] | None = None,
        add_files: Callable[[], None] | None = None,
        add_folder: Callable[[], None] | None = None,
        edit_settings: Callable[[], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._explorer = explorer
        self._widgets = widgets
        self._set_document_filter = set_document_filter
        self._is_busy = is_busy
        self._show_translations = show_translations
        self._open_source_path = open_source_path or (lambda _path: None)
        self._refresh_selected = refresh_selected or (lambda: None)
        self._export_selected = export_selected or (lambda: None)
        self._remove_selected = remove_selected or (lambda: None)
        self._add_files = add_files or (lambda: None)
        self._add_folder = add_folder or (lambda: None)
        self._edit_settings = edit_settings or (lambda: None)

    def selection_changed(self, document_ids: frozenset[str]) -> None:
        self._set_document_filter(document_ids)
        self.refresh_details(document_ids)
        enabled = bool(document_ids) and not self._is_busy()
        self._widgets.export_selected_button.setEnabled(enabled)
        self._widgets.remove_selected_button.setEnabled(enabled)
        self._widgets.refresh_selected_button.setEnabled(enabled)
        self.update_count(document_ids)

    def filter_files(self, text: str) -> None:
        self._explorer.set_file_filter(text)
        self.update_count(self._explorer.selected_document_ids())

    def update_count(self, selected_ids: frozenset[str] | None = None) -> None:
        total = len(self._workspace.project.documents) if self._workspace.has_project else 0
        visible = len(self._explorer.visible_document_ids())
        selected = len(
            selected_ids
            if selected_ids is not None
            else self._explorer.selected_document_ids()
        )
        suffix = f" · {selected} selected" if selected else ""
        self._widgets.file_count.setText(f"{visible} / {total} files{suffix}")

    def open_document(self, document_id: object) -> None:
        if not isinstance(document_id, str):
            return
        self._explorer.select_documents((document_id,))
        self._show_translations()

    def refresh_details(self, document_ids: frozenset[str]) -> None:
        if not self._workspace.has_project or not document_ids:
            self._widgets.file_details.setText(
                "Select one or more project files.\n\n"
                "Ctrl+Click selects individual files; Shift+Click selects a range. "
                "Double-click a file to open its translations."
            )
            return
        documents = [
            document
            for document in self._workspace.project.documents
            if document.id in document_ids
        ]
        entries = [
            entry
            for entry in self._workspace.project.entries
            if entry.document_id in document_ids
        ]
        translated = sum(entry.translation is not None for entry in entries)
        approved = sum(entry.status is EntryStatus.APPROVED for entry in entries)
        locked = sum(entry.locked for entry in entries)
        if len(documents) == 1:
            document = documents[0]
            heading = (
                f"{document.name}\n\nFormat: {document.source_format.upper()}\n"
                f"Project path: {document.source_path}\n"
                f"Source location: {document.source_location or 'Not recorded'}"
            )
        else:
            heading = f"{len(documents)} files selected"
        percent = round(translated * 100 / len(entries)) if entries else 0
        self._widgets.file_details.setText(
            f"{heading}\n\nEntries: {len(entries)}\n"
            f"Translated: {translated} ({percent}%)\n"
            f"Approved: {approved}\nLocked: {locked}\n\n"
            "Use Export selected to write only these files in their original formats."
        )

    def selected_source_location(
        self, document_ids: frozenset[str]
    ) -> Path | None:
        if len(document_ids) != 1:
            return None
        document_id = next(iter(document_ids))
        document = next(
            (
                item
                for item in self._workspace.project.documents
                if item.id == document_id
            ),
            None,
        )
        if document is None or not document.source_location:
            return None
        return Path(document.source_location)

    def open_selected_source_location(
        self, document_ids: frozenset[str]
    ) -> None:
        source = self.selected_source_location(document_ids)
        if source is not None:
            self._open_source_path(source)

    def build_context_menu(self) -> QMenu:
        selected_ids = self._explorer.selected_document_ids()
        menu = QMenu(self._widgets.explorer)
        open_action = menu.addAction("Open translations")
        open_action.setEnabled(len(selected_ids) == 1)
        open_action.triggered.connect(
            lambda: self.open_document(next(iter(selected_ids), None))
        )
        source_action = menu.addAction("Open source location")
        source_action.setEnabled(
            len(selected_ids) == 1
            and self.selected_source_location(selected_ids) is not None
        )
        source_action.triggered.connect(
            lambda: self.open_selected_source_location(selected_ids)
        )
        refresh_action = menu.addAction("Refresh from source...")
        refresh_action.setEnabled(bool(selected_ids))
        refresh_action.triggered.connect(self._refresh_selected)
        export_action = menu.addAction("Export selected...")
        export_action.setEnabled(bool(selected_ids))
        export_action.triggered.connect(self._export_selected)
        remove_action = menu.addAction("Remove from project...")
        remove_action.setEnabled(bool(selected_ids))
        remove_action.triggered.connect(self._remove_selected)
        menu.addSeparator()
        select_all_action = menu.addAction("Select all files")
        select_all_action.triggered.connect(self._explorer.select_visible_documents)
        clear_action = menu.addAction("Clear selection")
        clear_action.setEnabled(bool(selected_ids))
        clear_action.triggered.connect(self._widgets.file_tree.clearSelection)
        menu.addSeparator()
        menu.addAction("Add files...", self._add_files)
        menu.addAction("Add folder...", self._add_folder)
        menu.addAction("Project settings...", self._edit_settings)
        return menu

    def show_context_menu(self, position: QPoint) -> None:
        if not self._workspace.has_project:
            return
        menu = self.build_context_menu()
        menu.exec(self._widgets.file_tree.viewport().mapToGlobal(position))

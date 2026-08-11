"""Interactive project overview and document selection."""

from __future__ import annotations

from collections.abc import Callable, Collection
from pathlib import PurePosixPath

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
)

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import TranslationEntry


class ProjectExplorerController(QObject):
    """Renders project metadata and lets users select project documents."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        view: QListWidget,
        selection_changed: Callable[[frozenset[str]], None] | None = None,
        parent: QObject | None = None,
        file_tree: QTreeWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._view = view
        self._view.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._selection_changed = selection_changed or (lambda document_ids: None)
        self._file_tree = file_tree
        self._file_filter = ""
        selection_view = self._file_tree or self._view
        selection_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        selection_view.itemSelectionChanged.connect(self._notify_selection)

    def refresh(self) -> None:
        selected_ids = self.selected_document_ids()
        list_scroll = self._view.verticalScrollBar().value()
        tree_scroll = (
            self._file_tree.verticalScrollBar().value()
            if self._file_tree is not None
            else None
        )
        self._view.blockSignals(True)
        self._view.clear()
        if self._file_tree is not None:
            self._file_tree.blockSignals(True)
            self._file_tree.clear()
        if not self._workspace.has_project:
            self._add_information("No project open")
            self._view.blockSignals(False)
            if self._file_tree is not None:
                self._file_tree.blockSignals(False)
            return
        project = self._workspace.project
        statistics = self._workspace.project_statistics()
        self._add_information(project.name)
        self._add_information(f"{project.source_language} -> {project.target_language}")
        profile = getattr(project, "profile", None)
        if profile is not None and profile.project_type:
            self._add_information(f"Type: {profile.project_type}")
        if profile is not None and profile.description:
            self._add_information(f"Description: {profile.description}")
        if profile is not None and profile.domain:
            self._add_information(f"Domain: {profile.domain}")
        if profile is not None and profile.tone:
            self._add_information(f"Tone: {profile.tone}")
        self._add_information(
            f"Progress: {statistics.completion_percent}% "
            f"({statistics.translated_entries}/{statistics.total_entries})"
        )
        self._add_information(f"Untranslated: {statistics.untranslated_entries}")
        self._add_information(f"Needs review: {statistics.needs_review_entries}")
        self._add_information(f"Approved: {statistics.approved_entries}")
        self._add_information(f"Errors: {statistics.error_entries}")
        self._add_information(f"Validation issues: {statistics.entries_with_issues}")
        self._add_information(f"Locked: {statistics.locked_entries}")
        self._add_information(f"Files ({len(project.documents)}):")
        if not project.documents:
            self._add_information("No files yet — use File > Add files to project")
        progress_by_document = self._document_progress(project.entries)
        for document in project.documents:
            if self._file_tree is None:
                total, translated = progress_by_document.get(document.id, (0, 0))
                source_path = getattr(document, "source_path", document.name)
                item = QListWidgetItem(
                    f"  {source_path} [{document.source_format.upper()}] — "
                    f"{translated}/{total} translated"
                )
                item.setData(Qt.ItemDataRole.UserRole, document.id)
                item.setToolTip(source_path)
                self._view.addItem(item)
                item.setSelected(document.id in selected_ids)
        if self._file_tree is not None:
            self._populate_file_tree(
                project.documents, progress_by_document, selected_ids
            )
            self._file_tree.blockSignals(False)
            if tree_scroll is not None:
                self._file_tree.verticalScrollBar().setValue(tree_scroll)
        self._view.blockSignals(False)
        self._view.verticalScrollBar().setValue(list_scroll)

    def selected_document_ids(self) -> frozenset[str]:
        selected: set[str] = set()
        values: list[object] = []
        if self._file_tree is None:
            values.extend(
                item.data(Qt.ItemDataRole.UserRole)
                for item in self._view.selectedItems()
            )
        else:
            values.extend(
                item.data(0, Qt.ItemDataRole.UserRole)
                for item in self._file_tree.selectedItems()
            )
        for value in values:
            if isinstance(value, str):
                selected.add(value)
            elif isinstance(value, list):
                selected.update(item for item in value if isinstance(item, str))
        return frozenset(selected)

    def select_documents(self, document_ids: Collection[str]) -> None:
        selected = frozenset(document_ids)
        if self._file_tree is None:
            for index in range(self._view.count()):
                item = self._view.item(index)
                item.setSelected(item.data(Qt.ItemDataRole.UserRole) in selected)
            return
        iterator = QTreeWidgetItemIterator(self._file_tree)
        while iterator.value() is not None:
            tree_item = iterator.value()
            value = tree_item.data(0, Qt.ItemDataRole.UserRole)
            tree_item.setSelected(isinstance(value, str) and value in selected)
            iterator += 1

    def set_file_filter(self, text: str) -> None:
        self._file_filter = text.strip().casefold()
        if self._file_tree is not None:
            for index in range(self._file_tree.topLevelItemCount()):
                item = self._file_tree.topLevelItem(index)
                if item is not None:
                    self._filter_tree_item(item)

    def select_visible_documents(self) -> None:
        if self._file_tree is None:
            return
        self._file_tree.clearSelection()
        iterator = QTreeWidgetItemIterator(self._file_tree)
        while iterator.value() is not None:
            item = iterator.value()
            value = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(value, str) and not item.isHidden():
                item.setSelected(True)
            iterator += 1

    def visible_document_ids(self) -> frozenset[str]:
        if self._file_tree is None:
            return frozenset()
        visible: set[str] = set()
        iterator = QTreeWidgetItemIterator(self._file_tree)
        while iterator.value() is not None:
            item = iterator.value()
            value = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(value, str) and not item.isHidden():
                visible.add(value)
            iterator += 1
        return frozenset(visible)

    def _add_information(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self._view.addItem(item)

    def _notify_selection(self) -> None:
        self._selection_changed(self.selected_document_ids())

    def _populate_file_tree(
        self,
        documents: Collection[ProjectDocument],
        progress_by_document: dict[str, tuple[int, int]],
        selected_ids: Collection[str],
    ) -> None:
        if self._file_tree is None:
            return
        folders: dict[tuple[str, ...], QTreeWidgetItem] = {}
        folder_documents: dict[tuple[str, ...], list[str]] = {}
        for document in documents:
            source_path = str(getattr(document, "source_path", document.name))
            parts = PurePosixPath(source_path).parts
            parent: QTreeWidgetItem | None = None
            for depth, part in enumerate(parts[:-1], start=1):
                key = parts[:depth]
                folder_documents.setdefault(key, []).append(document.id)
                if key not in folders:
                    folder = QTreeWidgetItem((part, "Folder", ""))
                    if parent is not None:
                        parent.addChild(folder)
                    else:
                        self._file_tree.addTopLevelItem(folder)
                    folders[key] = folder
                parent = folders[key]
            total, translated = progress_by_document.get(document.id, (0, 0))
            percent = round(translated * 100 / total) if total else 0
            item = QTreeWidgetItem(
                (
                    parts[-1],
                    document.source_format.upper(),
                    f"{translated}/{total} ({percent}%)",
                )
            )
            item.setData(0, Qt.ItemDataRole.UserRole, document.id)
            item.setToolTip(0, source_path)
            if parent is not None:
                parent.addChild(item)
            else:
                self._file_tree.addTopLevelItem(item)
            item.setSelected(document.id in selected_ids)
        for key, item in folders.items():
            item.setData(0, Qt.ItemDataRole.UserRole, folder_documents[key])
            item.setExpanded(True)
        self.set_file_filter(self._file_filter)

    @staticmethod
    def _document_progress(
        entries: Collection[TranslationEntry],
    ) -> dict[str, tuple[int, int]]:
        progress: dict[str, tuple[int, int]] = {}
        for entry in entries:
            document_id = entry.document_id
            if document_id is None:
                continue
            total, translated = progress.get(document_id, (0, 0))
            progress[document_id] = (
                total + 1,
                translated + (entry.translation is not None),
            )
        return progress

    def _filter_tree_item(self, item: QTreeWidgetItem) -> tuple[str, ...]:
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(value, str):
            path = item.toolTip(0).casefold()
            visible = not self._file_filter or self._file_filter in path
            item.setHidden(not visible)
            return (value,) if visible else ()
        visible_ids = tuple(
            document_id
            for index in range(item.childCount())
            for document_id in self._filter_tree_item(item.child(index))
        )
        item.setData(0, Qt.ItemDataRole.UserRole, list(visible_ids))
        item.setHidden(not visible_ids)
        return visible_ids

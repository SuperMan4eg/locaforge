"""Translation revision history dock orchestration."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMessageBox, QPushButton, QWidget

from locaforge.application.project_workspace import ProjectWorkspace

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


class HistoryController(QObject):
    """Displays and restores revisions for the currently selected entry."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        revisions: QListWidget,
        operations: QListWidget,
        restore_button: QPushButton,
        run_action: ActionRunner,
        current_entry_id: Callable[[], str | None],
        can_restore: Callable[[], bool],
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._revisions = revisions
        self._operations = operations
        self._restore_button = restore_button
        self._run_action = run_action
        self._current_entry_id = current_entry_id
        self._can_restore = can_restore
        self._parent = parent
        revisions.currentItemChanged.connect(self._selection_changed)
        revisions.itemActivated.connect(self._activate_revision)
        restore_button.clicked.connect(self.restore)

    def refresh(self, entry_id: str) -> None:
        self._revisions.clear()
        for revision in self._workspace.entry_revisions(entry_id):
            timestamp = revision.recorded_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            translation = (
                revision.translation.replace("\n", " ")
                if revision.translation is not None
                else "<untranslated>"
            )
            item = QListWidgetItem(f"{timestamp} | {translation}")
            item.setData(Qt.ItemDataRole.UserRole, revision.revision_id)
            self._revisions.addItem(item)
        self._operations.clear()
        for operation in self._workspace.project_operations():
            timestamp = operation.recorded_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            state = "Undone" if operation.undone else "Applied"
            noun = "entry" if operation.entry_count == 1 else "entries"
            self._operations.addItem(
                f"{timestamp} | {state} | {operation.label} "
                f"({operation.entry_count} {noun})"
            )
        self._restore_button.setEnabled(False)

    def clear(self) -> None:
        self._revisions.clear()
        self._operations.clear()
        self._restore_button.setEnabled(False)

    def restore(self) -> None:
        entry_id = self._current_entry_id()
        item = self._revisions.currentItem()
        revision_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if entry_id is None or not isinstance(revision_id, int) or not self._can_restore():
            return
        if QMessageBox.question(
            self._parent,
            "Restore translation revision",
            "Replace the current translation with this previous version?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._run_action(
            lambda: self._workspace.restore_entry_revision(entry_id, revision_id),
            "Translation revision restored",
        )

    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        self._restore_button.setEnabled(current is not None and self._can_restore())

    def _activate_revision(self, item: QListWidgetItem) -> None:
        self._revisions.setCurrentItem(item)
        self.restore()

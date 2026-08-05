"""Editor for shared translation-memory records."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.translation_memory import TranslationMemoryRecord


class TranslationMemoryRecordDialog(QDialog):
    def __init__(
        self,
        record: TranslationMemoryRecord | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Translation Memory Record")
        self._source_language = QLineEdit(record.source_language if record else "", self)
        self._target_language = QLineEdit(record.target_language if record else "", self)
        self._source = QLineEdit(record.source if record else "", self)
        self._translation = QLineEdit(record.translation if record else "", self)
        self._context = QLineEdit(record.context if record else "", self)

        form = QFormLayout()
        form.addRow("Source language", self._source_language)
        form.addRow("Target language", self._target_language)
        form.addRow("Source", self._source)
        form.addRow("Translation", self._translation)
        form.addRow("Context", self._context)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def record(self) -> TranslationMemoryRecord:
        return TranslationMemoryRecord(
            self._source_language.text().strip(),
            self._target_language.text().strip(),
            self._source.text(),
            self._translation.text(),
            self._context.text(),
        )

    def _accept_if_valid(self) -> None:
        try:
            self.record()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid TM record", str(error))
            return
        self.accept()


class TranslationMemoryDialog(QDialog):
    def __init__(
        self, workspace: ProjectWorkspace, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self.setWindowTitle("Translation Memory")
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search source, translation, or context")
        self._search.textChanged.connect(self._refresh)
        self._records = QListWidget(self)
        self._records.itemDoubleClicked.connect(self._edit_record)

        add_button = QPushButton("Add", self)
        add_button.clicked.connect(self._add_record)
        edit_button = QPushButton("Edit", self)
        edit_button.clicked.connect(self._edit_selected_record)
        delete_button = QPushButton("Delete", self)
        delete_button.clicked.connect(self._delete_selected_record)
        refresh_button = QPushButton("Refresh", self)
        refresh_button.clicked.connect(self._refresh)

        actions = QHBoxLayout()
        for button in (add_button, edit_button, delete_button, refresh_button):
            actions.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._search)
        layout.addWidget(self._records)
        layout.addLayout(actions)
        self.resize(760, 520)
        self._refresh()

    def _refresh(self) -> None:
        self._records.clear()
        records = self._workspace.translation_memory_records(search=self._search.text())
        for record in records:
            context = f" [{record.context}]" if record.context else ""
            item = QListWidgetItem(
                f"{record.source_language} → {record.target_language}{context}\n"
                f"{record.source}\n{record.translation}"
            )
            item.setData(Qt.ItemDataRole.UserRole, record)
            self._records.addItem(item)

    def _selected_record(self) -> TranslationMemoryRecord | None:
        item = self._records.currentItem()
        record = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return record if isinstance(record, TranslationMemoryRecord) else None

    def _add_record(self) -> None:
        dialog = TranslationMemoryRecordDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._workspace.store_translation_memory_record(dialog.record())
        self._refresh()

    def _edit_selected_record(self) -> None:
        record = self._selected_record()
        if record is not None:
            self._edit_record(self._records.currentItem())

    def _edit_record(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        original = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(original, TranslationMemoryRecord):
            return
        dialog = TranslationMemoryRecordDialog(original, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        updated = dialog.record()
        self._workspace.store_translation_memory_record(updated)
        if updated != original and (
            updated.source_language,
            updated.target_language,
            updated.source,
            updated.context,
        ) != (
            original.source_language,
            original.target_language,
            original.source,
            original.context,
        ):
            self._workspace.delete_translation_memory_record(original)
        self._refresh()

    def _delete_selected_record(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        if QMessageBox.question(
            self,
            "Delete TM record",
            f"Delete translation memory record for:\n{record.source}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._workspace.delete_translation_memory_record(record)
        self._refresh()

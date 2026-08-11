"""Qt model for displaying translation entries."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)

from locaforge.domain.entry import TranslationEntry
from locaforge.presentation.localization import tr_source

_INVALID_INDEX = QModelIndex()


class TranslationTableModel(QAbstractTableModel):
    _HEADERS = ("Key", "Source", "Translation", "Status")
    status_role = int(Qt.ItemDataRole.UserRole) + 1
    _STATUS_LABELS = {
        "untranslated": "Untranslated",
        "translated": "Translated",
        "needs_review": "Needs review",
        "approved": "Approved",
        "error": "Error",
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: list[TranslationEntry] = []
        self._entry_rows: dict[str, int] = {}
        self._search_values: list[tuple[str, str, str, str]] = []

    def set_entries(self, entries: Sequence[TranslationEntry]) -> None:
        replacement = list(entries)
        entry_rows = self._build_entry_rows(replacement)
        search_values = [self._normalized_search_values(entry) for entry in replacement]
        self.beginResetModel()
        self._entries = replacement
        self._entry_rows = entry_rows
        self._search_values = search_values
        self.endResetModel()

    def entry_at(self, row: int) -> TranslationEntry:
        return self._entries[row]

    def update_entry(self, updated_entry: TranslationEntry) -> None:
        row = self._entry_rows.get(updated_entry.id)
        if row is None:
            raise KeyError(f"Entry {updated_entry.id!r} was not found in the table model")
        self._entries[row] = updated_entry
        self._search_values[row] = self._normalized_search_values(updated_entry)
        top_left = self.index(row, 0)
        bottom_right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right)

    def search_values_at(self, row: int) -> tuple[str, str, str, str]:
        """Return pre-normalized key, source, translation, and context text."""
        return self._search_values[row]

    @staticmethod
    def _build_entry_rows(entries: Sequence[TranslationEntry]) -> dict[str, int]:
        rows: dict[str, int] = {}
        for row, entry in enumerate(entries):
            if entry.id in rows:
                raise ValueError(f"Duplicate table entry id: {entry.id!r}")
            rows[entry.id] = row
        return rows

    @staticmethod
    def _normalized_search_values(entry: TranslationEntry) -> tuple[str, str, str, str]:
        key = entry.key or "/".join(str(part) for part in entry.key_path)
        return (
            key.casefold(),
            entry.source.casefold(),
            (entry.translation or "").casefold(),
            (entry.context or "").casefold(),
        )

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX
    ) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX
    ) -> int:
        return 0 if parent.isValid() else len(self._HEADERS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        if role == self.status_role:
            return entry.status.value if index.column() == 3 else None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        column = index.column()
        if column == 0:
            return entry.key or "/".join(str(part) for part in entry.key_path)
        if column == 1:
            return entry.source
        if column == 2:
            return entry.translation or ""
        return tr_source(self._STATUS_LABELS.get(entry.status.value, entry.status.value))

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return tr_source(self._HEADERS[section])
        return section + 1

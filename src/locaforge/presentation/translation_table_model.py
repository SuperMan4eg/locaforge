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

_INVALID_INDEX = QModelIndex()


class TranslationTableModel(QAbstractTableModel):
    _HEADERS = ("Key", "Source", "Translation", "Status")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: list[TranslationEntry] = []

    def set_entries(self, entries: Sequence[TranslationEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def entry_at(self, row: int) -> TranslationEntry:
        return self._entries[row]

    def update_entry(self, updated_entry: TranslationEntry) -> None:
        for row, entry in enumerate(self._entries):
            if entry.id != updated_entry.id:
                continue
            self._entries[row] = updated_entry
            top_left = self.index(row, 0)
            bottom_right = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right)
            return
        raise KeyError(f"Entry {updated_entry.id!r} was not found in the table model")

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
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        entry = self._entries[index.row()]
        values = (
            entry.key or "/".join(str(part) for part in entry.key_path),
            entry.source,
            entry.translation or "",
            entry.status.value,
        )
        return values[index.column()]

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._HEADERS[section]
        return section + 1

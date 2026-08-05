"""Search and status filtering for the translation table."""

from __future__ import annotations

from collections.abc import Collection
from typing import cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSortFilterProxyModel

from locaforge.presentation.translation_table_model import TranslationTableModel


class TranslationFilterProxyModel(QSortFilterProxyModel):
    _STATUS_ORDER = {
        "untranslated": 0,
        "error": 1,
        "needs_review": 2,
        "translated": 3,
        "approved": 4,
    }

    def __init__(self) -> None:
        super().__init__()
        self._search_text = ""
        self._statuses: frozenset[str] = frozenset()
        self._issue_entry_ids: frozenset[str] | None = None
        self.setDynamicSortFilter(True)

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip().casefold()
        self._invalidate_rows()

    def set_status(self, status: str | None) -> None:
        self.set_statuses(()) if status is None else self.set_statuses((status,))

    def set_statuses(self, statuses: set[str] | frozenset[str] | tuple[str, ...]) -> None:
        self._statuses = frozenset(statuses)
        self._invalidate_rows()

    def set_issue_entry_ids(self, entry_ids: Collection[str] | None) -> None:
        self._issue_entry_ids = None if entry_ids is None else frozenset(entry_ids)
        self._invalidate_rows()

    def _invalidate_rows(self) -> None:
        self.beginFilterChange()
        self.endFilterChange(self.Direction.Rows)

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        source_model = self.sourceModel()
        if source_model is None:
            return False
        translation_model = cast(TranslationTableModel, source_model)
        if self._issue_entry_ids is not None:
            entry = translation_model.entry_at(source_row)
            if entry.id not in self._issue_entry_ids:
                return False
        if self._statuses:
            status = source_model.data(source_model.index(source_row, 3, source_parent))
            if status not in self._statuses:
                return False
        if not self._search_text:
            return True
        searchable_values = (
            source_model.data(source_model.index(source_row, column, source_parent))
            for column in range(3)
        )
        context = translation_model.entry_at(source_row).context or ""
        return self._search_text in context.casefold() or any(
            self._search_text in str(value).casefold() for value in searchable_values
        )

    def lessThan(
        self,
        left: QModelIndex | QPersistentModelIndex,
        right: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if left.column() == 3:
            source_model = self.sourceModel()
            if source_model is not None:
                left_status = source_model.data(left)
                right_status = source_model.data(right)
                return self._STATUS_ORDER.get(str(left_status), 99) < self._STATUS_ORDER.get(
                    str(right_status), 99
                )
        return super().lessThan(left, right)

"""Search and status filtering for the translation table."""

from __future__ import annotations

from collections.abc import Collection
from typing import cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSortFilterProxyModel

from locaforge.presentation.translation_table_model import TranslationTableModel


class TranslationFilterProxyModel(QSortFilterProxyModel):
    _SEARCH_FIELD_INDEX = {
        "key": 0,
        "source": 1,
        "translation": 2,
        "context": 3,
    }
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
        self._search_field = "all"
        self._statuses: frozenset[str] = frozenset()
        self._document_ids: frozenset[str] = frozenset()
        self._issue_entry_ids: frozenset[str] | None = None
        self.setDynamicSortFilter(True)

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip().casefold()
        self._invalidate_rows()

    def set_search_field(self, field: str) -> None:
        if field not in {"all", "key", "source", "translation", "context"}:
            raise ValueError(f"Unsupported search field: {field!r}")
        self._search_field = field
        self._invalidate_rows()

    def set_status(self, status: str | None) -> None:
        self.set_statuses(()) if status is None else self.set_statuses((status,))

    def set_statuses(self, statuses: set[str] | frozenset[str] | tuple[str, ...]) -> None:
        self._statuses = frozenset(statuses)
        self._invalidate_rows()

    def set_issue_entry_ids(self, entry_ids: Collection[str] | None) -> None:
        self._issue_entry_ids = None if entry_ids is None else frozenset(entry_ids)
        self._invalidate_rows()

    def set_document_id(self, document_id: str | None) -> None:
        self.set_document_ids(()) if document_id is None else self.set_document_ids((document_id,))

    def set_document_ids(self, document_ids: Collection[str]) -> None:
        self._document_ids = frozenset(document_ids)
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
        entry = translation_model.entry_at(source_row)
        if self._document_ids:
            if entry.document_id not in self._document_ids:
                return False
        if self._issue_entry_ids is not None:
            if entry.id not in self._issue_entry_ids:
                return False
        if self._statuses:
            if entry.status.value not in self._statuses:
                return False
        if not self._search_text:
            return True
        values = translation_model.search_values_at(source_row)
        if self._search_field == "all":
            return any(self._search_text in value for value in values)
        return self._search_text in values[self._SEARCH_FIELD_INDEX[self._search_field]]

    def lessThan(
        self,
        left: QModelIndex | QPersistentModelIndex,
        right: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if left.column() == 3:
            source_model = self.sourceModel()
            if isinstance(source_model, TranslationTableModel):
                left_status = source_model.entry_at(left.row()).status.value
                right_status = source_model.entry_at(right.row()).status.value
                return self._STATUS_ORDER.get(left_status, 99) < self._STATUS_ORDER.get(
                    right_status, 99
                )
        return super().lessThan(left, right)

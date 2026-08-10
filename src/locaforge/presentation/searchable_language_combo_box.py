"""A searchable, selection-only language picker."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget

from locaforge.presentation.language_registry import (
    LANGUAGES,
    Language,
    canonical_bcp47,
    language_for_code,
)


class _LanguageFilterModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.query = ""

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        if not self.query:
            return True
        model = self.sourceModel()
        if model is None:
            return False
        # The language catalogue is a flat model, so every accepted row is root-level.
        index = model.index(source_row, 0)
        name = str(index.data(SearchableLanguageComboBox.name_role))
        code = str(index.data(SearchableLanguageComboBox.code_role))
        return self.query in name.casefold() or self.query in code.casefold()


class SearchableLanguageComboBox(QComboBox):
    """Filters language names and codes while accepting only list selections."""

    name_role = int(Qt.ItemDataRole.UserRole) + 1
    code_role = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(self, language_code: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_code: str | None = None
        self._filtering = False
        self._source_model = QStandardItemModel(self)
        self._proxy_model = _LanguageFilterModel(self)
        self._proxy_model.setSourceModel(self._source_model)
        self.setModel(self._proxy_model)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._line_edit().setPlaceholderText("Type a language name or code")
        self._line_edit().textEdited.connect(self._filter_languages)
        self.currentIndexChanged.connect(self._selection_changed)
        for language in LANGUAGES:
            self._add_language(language)
        self.set_language_code(language_code)

    def language_code(self) -> str | None:
        """The selected canonical code, or ``None`` when only a query was typed."""

        return self._selected_code

    # Compatibility with the former QLineEdit fields.
    def text(self) -> str:
        return self._line_edit().text()

    def setText(self, value: str) -> None:
        self.set_language_code(value)

    def set_language_code(self, value: str) -> None:
        """Select a registered language, preserving old unknown values temporarily."""

        raw_value = value.strip()
        if not raw_value:
            self._selected_code = None
            self._set_filter("")
            self.setCurrentIndex(-1)
            self._line_edit().clear()
            return
        canonical = canonical_bcp47(raw_value)
        stored_value = canonical or raw_value
        language = language_for_code(stored_value)
        if language is None:
            language = Language("Unknown language (temporary)", stored_value)
        self._add_language(language)
        self._set_filter("")
        self.setCurrentIndex(self.findData(stored_value, self.code_role))
        self._selected_code = stored_value

    def _add_language(self, language: Language) -> None:
        if self._source_model.findItems(language.code, Qt.MatchFlag.MatchExactly, self.code_role):
            return
        item = QStandardItem(language.label)
        item.setData(language.name, self.name_role)
        item.setData(language.code, self.code_role)
        self._source_model.appendRow(item)

    def _filter_languages(self, query: str) -> None:
        self._selected_code = None
        self._set_filter(query)
        self.showPopup()

    def _set_filter(self, query: str) -> None:
        self._filtering = True
        try:
            self._proxy_model.query = query.strip().casefold()
            # Updating the base class filter causes it to reevaluate our custom
            # name/code predicate without using deprecated invalidateFilter().
            self._proxy_model.setFilterFixedString(query)
        finally:
            self._filtering = False

    def _selection_changed(self, index: int) -> None:
        if self._filtering:
            return
        if index < 0:
            self._selected_code = None
            return
        code = self.itemData(index, self.code_role)
        self._selected_code = str(code) if code is not None else None

    def _line_edit(self) -> QLineEdit:
        line_edit = self.lineEdit()
        assert line_edit is not None
        return line_edit

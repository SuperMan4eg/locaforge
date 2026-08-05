"""Translation table filter widgets and interaction orchestration."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QToolButton,
    QWidget,
)

from locaforge.domain.entry import TranslationEntry
from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
from locaforge.presentation.translation_table_model import TranslationTableModel


class TranslationFilterController(QObject):
    """Owns search, status, and validation-issue filters for the table."""

    _STATUSES = (
        ("Untranslated", "untranslated"),
        ("Translated", "translated"),
        ("Needs review", "needs_review"),
        ("Approved", "approved"),
        ("Error", "error"),
    )

    def __init__(
        self,
        source_model: TranslationTableModel,
        proxy_model: TranslationFilterProxyModel,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self._source_model = source_model
        self._proxy_model = proxy_model
        self._issue_entry_ids: frozenset[str] = frozenset()

        self.search = QLineEdit(parent)
        self.search.setPlaceholderText(
            "Search key, source, translation, or context (Ctrl+F)"
        )
        self.search.textChanged.connect(self._set_search_filter)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_search_filter)

        self.status_button = QToolButton(parent)
        self.status_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        status_menu = QMenu(parent)
        self.status_button.setMenu(status_menu)
        self._status_actions: dict[str, QAction] = {}
        self._status_labels: dict[str, str] = {}
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(180)
        self._status_timer.timeout.connect(self._apply_status_filter)
        for label, status in self._STATUSES:
            action = QAction(label, parent)
            action.setCheckable(True)
            action.toggled.connect(self._status_filter_changed)
            status_menu.addAction(action)
            self._status_actions[status] = action
            self._status_labels[status] = label
        self._update_status_label()

        self.issues_button = QToolButton(parent)
        self.issues_button.setCheckable(True)
        self.issues_button.setToolTip("Show only entries with validation issues")
        self.issues_button.toggled.connect(self._apply_issue_filter)
        self._update_issue_label()

        self.clear_button = QToolButton(parent)
        self.clear_button.setText("Clear filters")
        self.clear_button.setToolTip("Clear table filters (Ctrl+Shift+F)")
        self.clear_button.clicked.connect(self.clear)
        self.result_count = QLabel("0 / 0 entries", parent)

        proxy_model.modelReset.connect(self.refresh_result_count)
        proxy_model.rowsInserted.connect(self.refresh_result_count)
        proxy_model.rowsRemoved.connect(self.refresh_result_count)
        self._update_controls()

    def add_to_layout(self, layout: QHBoxLayout) -> None:
        layout.addWidget(self.search)
        layout.addWidget(self.status_button)
        layout.addWidget(self.issues_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.result_count)

    def clear(self) -> None:
        self.search.clear()
        self._search_timer.stop()
        self._apply_search_filter()
        self.clear_statuses()
        self.issues_button.setChecked(False)
        self._update_controls()

    def clear_text_and_statuses(self) -> None:
        self.search.clear()
        self.clear_statuses()

    def clear_statuses(self) -> None:
        self._status_timer.stop()
        for action in self._status_actions.values():
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)
        self._apply_status_filter()
        self._update_status_label()
        self._update_controls()

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def set_issue_entries(self, entry_ids: Collection[str]) -> None:
        self._issue_entry_ids = frozenset(entry_ids)
        self._update_issue_label()
        if self.issues_button.isChecked():
            self._proxy_model.set_issue_entry_ids(self._issue_entry_ids)

    def set_issues_only(self, enabled: bool) -> None:
        self.issues_button.setChecked(enabled)

    def set_issues_enabled(self, enabled: bool) -> None:
        self.issues_button.setEnabled(enabled)

    def update_entries(self, entries: Sequence[TranslationEntry]) -> None:
        counts = Counter(entry.status.value for entry in entries)
        for status, action in self._status_actions.items():
            action.setText(f"{self._status_labels[status]} ({counts[status]})")
        self._update_status_label()
        self.refresh_result_count()
        self._update_controls()

    def refresh_result_count(self) -> None:
        self.result_count.setText(
            f"{self._proxy_model.rowCount()} / {self._source_model.rowCount()} entries"
        )

    def _set_search_filter(self, text: str) -> None:
        self._update_controls()
        if not text.strip():
            self._search_timer.stop()
            self._apply_search_filter()
            return
        self._search_timer.start()

    def _apply_search_filter(self) -> None:
        self._proxy_model.set_search_text(self.search.text())

    def _status_filter_changed(self, selected: bool) -> None:
        del selected
        self._status_timer.start()
        self._update_status_label()
        self._update_controls()

    def _apply_status_filter(self) -> None:
        selected = {
            status for status, action in self._status_actions.items() if action.isChecked()
        }
        self._proxy_model.set_statuses(selected)

    def _apply_issue_filter(self, enabled: bool) -> None:
        self._proxy_model.set_issue_entry_ids(self._issue_entry_ids if enabled else None)
        self._update_controls()

    def _update_controls(self) -> None:
        has_filters = (
            bool(self.search.text().strip())
            or any(action.isChecked() for action in self._status_actions.values())
            or self.issues_button.isChecked()
        )
        self.clear_button.setEnabled(has_filters)

    def _update_status_label(self) -> None:
        selected = [action for action in self._status_actions.values() if action.isChecked()]
        if not selected:
            self.status_button.setText("All statuses")
        elif len(selected) == 1:
            status = next(
                status
                for status, action in self._status_actions.items()
                if action is selected[0]
            )
            self.status_button.setText(self._status_labels[status])
        else:
            self.status_button.setText(f"{len(selected)} statuses")

    def _update_issue_label(self) -> None:
        self.issues_button.setText(f"Issues only ({len(self._issue_entry_ids)})")

"""Validation and QA panel presentation orchestration."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QComboBox, QLabel, QListWidget, QListWidgetItem, QPushButton

from locaforge.application.dto.validation import EntryValidationIssue, ValidationCode
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import EntryStatus
from locaforge.presentation.translation_filter_controller import TranslationFilterController
from locaforge.presentation.validation_filter import (
    filter_validation_issues,
    format_validation_issues,
    group_attention_issues,
)


class QualityPanelController(QObject):
    """Owns validation issue grouping and current-entry QA controls."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        category_filter: QComboBox,
        issue_list: QListWidget,
        current_issues: QLabel,
        dismiss_ai_button: QPushButton,
        retranslate_button: QPushButton,
        apply_matching_button: QPushButton,
        table_filters: TranslationFilterController,
        current_entry_id: Callable[[], str | None],
        is_busy: Callable[[], bool],
        select_entry: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._category_filter = category_filter
        self._issue_list = issue_list
        self._current_issues = current_issues
        self._dismiss_ai_button = dismiss_ai_button
        self._retranslate_button = retranslate_button
        self._apply_matching_button = apply_matching_button
        self._table_filters = table_filters
        self._current_entry_id = current_entry_id
        self._is_busy = is_busy
        self._select_entry = select_entry
        self._issues_by_entry: dict[str, tuple[EntryValidationIssue, ...]] = {}
        category_filter.currentIndexChanged.connect(self.refresh)
        issue_list.itemActivated.connect(self._activate_issue)

    @property
    def issues_by_entry(self) -> Mapping[str, tuple[EntryValidationIssue, ...]]:
        return self._issues_by_entry

    def refresh(self) -> None:
        self._issue_list.clear()
        self._issues_by_entry.clear()
        if not self._workspace.has_project:
            self._table_filters.set_issue_entries(())
            self.refresh_current()
            return
        entries_by_id = {entry.id: entry for entry in self._workspace.project.entries}
        all_issues = self._workspace.validation_issues()
        grouped_issues: dict[str, list[EntryValidationIssue]] = {}
        for issue in all_issues:
            grouped_issues.setdefault(issue.entry_id, []).append(issue)
        self._issues_by_entry = {
            entry_id: tuple(issues) for entry_id, issues in grouped_issues.items()
        }
        self._table_filters.set_issue_entries(self._issues_by_entry)
        category = self._category_filter.currentData()
        issues = filter_validation_issues(
            all_issues,
            category if isinstance(category, str) else None,
        )
        if category == "attention":
            issue_groups = group_attention_issues(issues)
        else:
            issue_groups = tuple(group_attention_issues((issue,))[0] for issue in issues)
        for issue_group in issue_groups:
            entry = entries_by_id.get(issue_group.entry_ids[0])
            path = (
                "/".join(str(part) for part in entry.key_path)
                if entry is not None
                else issue_group.entry_ids[0]
            )
            if len(issue_group.entry_ids) > 1:
                source = entry.source.replace("\n", " ") if entry is not None else path
                text = (
                    f"{len(issue_group.entry_ids)} entries | {source} — "
                    f"[{issue_group.code.value}] {issue_group.message}"
                )
            else:
                text = f"{path} — [{issue_group.code.value}] {issue_group.message}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, issue_group.entry_ids)
            self._issue_list.addItem(item)
        self.refresh_current()

    def refresh_current(self) -> None:
        entry_id = self._current_entry_id()
        if entry_id is None or not self._workspace.has_project:
            self._current_issues.setText("No validation issues")
            self._dismiss_ai_button.setEnabled(False)
            self._retranslate_button.setEnabled(False)
            self._apply_matching_button.setEnabled(False)
            return
        issues = self._issues_by_entry.get(entry_id, ())
        self._current_issues.setText(format_validation_issues(issues))
        busy = self._is_busy()
        self._dismiss_ai_button.setEnabled(
            not busy and any(issue.code is ValidationCode.AI_REVIEW for issue in issues)
        )
        entry = self._workspace.project.get_entry(entry_id)
        self._retranslate_button.setEnabled(
            not busy and not entry.locked and entry.status is not EntryStatus.APPROVED
        )
        matching_count = sum(
            not candidate.locked
            and candidate.source == entry.source
            and candidate.context == entry.context
            for candidate in self._workspace.project.entries
        )
        self._apply_matching_button.setEnabled(
            not busy
            and not entry.locked
            and entry.translation is not None
            and matching_count > 1
            and any(
                issue.code is ValidationCode.INCONSISTENT_TRANSLATION
                for issue in issues
            )
        )

    def _activate_issue(self, item: QListWidgetItem) -> None:
        entry_ids = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry_ids, tuple) or not entry_ids:
            return
        entry_id = entry_ids[0]
        if isinstance(entry_id, str):
            self._select_entry(entry_id)

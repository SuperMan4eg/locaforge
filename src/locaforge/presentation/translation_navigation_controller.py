"""Translation and quality-issue navigation orchestration."""

from __future__ import annotations

from collections.abc import Callable, Collection

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import EntryStatus
from locaforge.presentation.translation_navigation import (
    adjacent_row_index,
    next_matching_entry_id,
)


class TranslationNavigationController:
    """Selects adjacent, problematic, and actionable translation entries."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        current_entry_id: Callable[[], str | None],
        is_busy: Callable[[], bool],
        current_row: Callable[[], int],
        row_count: Callable[[], int],
        select_row: Callable[[int], None],
        issue_entry_ids: Callable[[], Collection[str]],
        select_entry: Callable[[str], None],
        clear_issues_only: Callable[[], None],
        show_status: Callable[[str, int], None],
        apply_translation: Callable[[], bool],
    ) -> None:
        self._workspace = workspace
        self._current_entry_id = current_entry_id
        self._is_busy = is_busy
        self._current_row = current_row
        self._row_count = row_count
        self._select_row = select_row
        self._issue_entry_ids = issue_entry_ids
        self._select_entry = select_entry
        self._clear_issues_only = clear_issues_only
        self._show_status = show_status
        self._apply_translation = apply_translation

    def apply_and_select_next(self) -> None:
        if self._apply_translation():
            self.select_relative_entry(1)

    def select_relative_entry(self, offset: int) -> None:
        target_row = adjacent_row_index(self._current_row(), self._row_count(), offset)
        if target_row is not None:
            self._select_row(target_row)

    def select_relative_issue(self, offset: int) -> None:
        if not self._workspace.has_project or self._is_busy():
            return
        entry_id = next_matching_entry_id(
            tuple(entry.id for entry in self._workspace.project.entries),
            self._current_entry_id(),
            self._issue_entry_ids(),
            offset,
        )
        if entry_id is None:
            self._show_status("No validation issues", 3000)
            return
        self._select_entry(entry_id)

    def select_next_actionable_entry(self) -> None:
        if not self._workspace.has_project or self._is_busy():
            return
        actionable_statuses = {
            EntryStatus.UNTRANSLATED,
            EntryStatus.NEEDS_REVIEW,
            EntryStatus.ERROR,
        }
        entries = self._workspace.project.entries
        entry_id = next_matching_entry_id(
            tuple(entry.id for entry in entries),
            self._current_entry_id(),
            {
                entry.id
                for entry in entries
                if not entry.locked and entry.status in actionable_statuses
            },
            1,
        )
        if entry_id is None:
            self._show_status("No actionable entries", 3000)
            return
        self._clear_issues_only()
        self._select_entry(entry_id)

"""Bulk operations for entries with quality-assurance issues."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from locaforge.application.dto.validation import EntryValidationIssue, ValidationCode
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import EntryStatus

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


class QaEntryOperationsController:
    """Coordinates selection, retranslation, and dismissal of QA entries."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        is_busy: Callable[[], bool],
        issues_by_entry: Callable[[], Mapping[str, tuple[EntryValidationIssue, ...]]],
        selected_entry_ids: Callable[[], Sequence[str]],
        clear_filters: Callable[[], None],
        show_issues_only: Callable[[], None],
        visible_row_count: Callable[[], int],
        select_all_visible: Callable[[], None],
        start_translation: Callable[[tuple[str, ...]], object],
        run_action: ActionRunner,
        show_status: Callable[[str, int], None],
        show_information: Callable[[str, str], None],
        confirm_retranslation: Callable[[int], bool],
        confirm_dismissal: Callable[[int], bool],
    ) -> None:
        self._workspace = workspace
        self._is_busy = is_busy
        self._issues_by_entry = issues_by_entry
        self._selected_entry_ids = selected_entry_ids
        self._clear_filters = clear_filters
        self._show_issues_only = show_issues_only
        self._visible_row_count = visible_row_count
        self._select_all_visible = select_all_visible
        self._start_translation = start_translation
        self._run_action = run_action
        self._show_status = show_status
        self._show_information = show_information
        self._confirm_retranslation = confirm_retranslation
        self._confirm_dismissal = confirm_dismissal

    def select_all_qa_entries(self) -> None:
        if not self._can_run():
            return
        self._clear_filters()
        self._show_issues_only()
        issue_count = self._visible_row_count()
        if not issue_count:
            self._show_status("No entries with QA issues", 3000)
            return
        self._select_all_visible()
        self._show_status(f"Selected {issue_count} entries with QA issues", 3000)

    def retranslate_all_qa_entries(self) -> None:
        if not self._can_run():
            return
        issue_entry_ids = self._issues_by_entry()
        entry_ids = tuple(
            entry.id
            for entry in self._workspace.project.entries
            if entry.id in issue_entry_ids
            and not entry.locked
            and entry.status is not EntryStatus.APPROVED
        )
        if not entry_ids:
            self._show_information(
                "Batch translation", "There are no editable entries with QA issues."
            )
            return
        if self._confirm_retranslation(len(entry_ids)):
            self._start_translation(entry_ids)

    def dismiss_selected_ai_issues(self) -> None:
        if not self._can_run():
            return
        issues_by_entry = self._issues_by_entry()
        entry_ids = tuple(
            entry_id
            for entry_id in self._selected_entry_ids()
            if any(
                issue.code is ValidationCode.AI_REVIEW
                for issue in issues_by_entry.get(entry_id, ())
            )
        )
        if not entry_ids:
            self._show_information(
                "AI review", "Select entries with AI review issues."
            )
            return
        if not self._confirm_dismissal(len(entry_ids)):
            return
        self._run_action(
            lambda: self._workspace.dismiss_ai_review_issues(entry_ids),
            "Selected AI review issues dismissed",
        )

    def _can_run(self) -> bool:
        return self._workspace.has_project and not self._is_busy()

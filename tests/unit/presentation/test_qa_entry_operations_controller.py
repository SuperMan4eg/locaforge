from types import SimpleNamespace
from typing import Any, cast

from locaforge.application.dto.validation import EntryValidationIssue, ValidationCode
from locaforge.domain.entry import EntryStatus
from locaforge.presentation.qa_entry_operations_controller import (
    QaEntryOperationsController,
)


def entry(
    entry_id: str,
    status: EntryStatus = EntryStatus.TRANSLATED,
    *,
    locked: bool = False,
):
    return SimpleNamespace(id=entry_id, status=status, locked=locked)


def issue(entry_id: str, code: ValidationCode) -> EntryValidationIssue:
    return EntryValidationIssue(entry_id, code, "issue")


class WorkspaceStub:
    def __init__(self, entries=(), *, has_project: bool = True) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(entries=tuple(entries))
        self.dismissed: tuple[str, ...] | None = None

    def dismiss_ai_review_issues(self, entry_ids: tuple[str, ...]) -> None:
        self.dismissed = entry_ids


def make_controller(
    workspace: WorkspaceStub,
    *,
    issues=None,
    selected: tuple[str, ...] = (),
    busy: bool = False,
    row_count: int = 0,
    confirm_retranslation: bool = True,
    confirm_dismissal: bool = True,
):
    issues = issues or {}
    filter_calls: list[str] = []
    selected_all: list[bool] = []
    translations: list[tuple[str, ...]] = []
    messages: list[str] = []
    statuses: list[tuple[str, int]] = []
    information: list[tuple[str, str]] = []
    retranslation_counts: list[int] = []
    dismissal_counts: list[int] = []

    def run_action(action, message: str) -> bool:
        action()
        messages.append(message)
        return True

    controller = QaEntryOperationsController(
        cast(Any, workspace),
        is_busy=lambda: busy,
        issues_by_entry=lambda: issues,
        selected_entry_ids=lambda: selected,
        clear_filters=lambda: filter_calls.append("clear"),
        show_issues_only=lambda: filter_calls.append("issues"),
        visible_row_count=lambda: row_count,
        select_all_visible=lambda: selected_all.append(True),
        start_translation=lambda entry_ids: translations.append(entry_ids),
        run_action=run_action,
        show_status=lambda message, timeout: statuses.append((message, timeout)),
        show_information=lambda title, message: information.append((title, message)),
        confirm_retranslation=lambda count: (
            retranslation_counts.append(count) or confirm_retranslation
        ),
        confirm_dismissal=lambda count: (
            dismissal_counts.append(count) or confirm_dismissal
        ),
    )
    return (
        controller,
        filter_calls,
        selected_all,
        translations,
        messages,
        statuses,
        information,
        retranslation_counts,
        dismissal_counts,
    )


def test_select_all_qa_entries_applies_filter_and_selects_visible_rows() -> None:
    controller, filters, selected_all, _, _, statuses, _, _, _ = make_controller(
        WorkspaceStub(), row_count=3
    )

    controller.select_all_qa_entries()

    assert filters == ["clear", "issues"]
    assert selected_all == [True]
    assert statuses == [("Selected 3 entries with QA issues", 3000)]


def test_select_all_reports_when_filter_has_no_rows() -> None:
    controller, filters, selected_all, _, _, statuses, _, _, _ = make_controller(
        WorkspaceStub()
    )

    controller.select_all_qa_entries()

    assert filters == ["clear", "issues"]
    assert selected_all == []
    assert statuses == [("No entries with QA issues", 3000)]


def test_retranslate_qa_excludes_locked_and_approved_entries() -> None:
    entries = (
        entry("entry-1"),
        entry("entry-2", locked=True),
        entry("entry-3", EntryStatus.APPROVED),
        entry("entry-4"),
    )
    issues = {
        "entry-1": (issue("entry-1", ValidationCode.EMPTY_TRANSLATION),),
        "entry-2": (issue("entry-2", ValidationCode.EMPTY_TRANSLATION),),
        "entry-3": (issue("entry-3", ValidationCode.EMPTY_TRANSLATION),),
    }
    controller, _, _, translations, _, _, _, counts, _ = make_controller(
        WorkspaceStub(entries), issues=issues
    )

    controller.retranslate_all_qa_entries()

    assert counts == [1]
    assert translations == [("entry-1",)]


def test_retranslate_reports_empty_or_honors_cancel() -> None:
    empty, *empty_results = make_controller(WorkspaceStub((entry("entry-1"),)))
    issues = {"entry-1": (issue("entry-1", ValidationCode.EMPTY_TRANSLATION),)}
    cancelled, _, _, translations, _, _, _, counts, _ = make_controller(
        WorkspaceStub((entry("entry-1"),)),
        issues=issues,
        confirm_retranslation=False,
    )

    empty.retranslate_all_qa_entries()
    cancelled.retranslate_all_qa_entries()

    assert empty_results[5] == [
        ("Batch translation", "There are no editable entries with QA issues.")
    ]
    assert counts == [1]
    assert translations == []


def test_dismiss_selected_keeps_only_entries_with_ai_review_issue() -> None:
    workspace = WorkspaceStub()
    issues = {
        "entry-1": (issue("entry-1", ValidationCode.AI_REVIEW),),
        "entry-2": (issue("entry-2", ValidationCode.EMPTY_TRANSLATION),),
        "entry-3": (
            issue("entry-3", ValidationCode.EMPTY_TRANSLATION),
            issue("entry-3", ValidationCode.AI_REVIEW),
        ),
    }
    controller, _, _, _, messages, _, _, _, counts = make_controller(
        workspace,
        issues=issues,
        selected=("entry-1", "entry-2", "entry-3"),
    )

    controller.dismiss_selected_ai_issues()

    assert counts == [2]
    assert workspace.dismissed == ("entry-1", "entry-3")
    assert messages == ["Selected AI review issues dismissed"]


def test_dismiss_reports_empty_selection_and_honors_cancel() -> None:
    issue_map = {"entry-1": (issue("entry-1", ValidationCode.AI_REVIEW),)}
    empty_workspace = WorkspaceStub()
    empty, _, _, _, _, _, information, _, _ = make_controller(empty_workspace)
    cancelled_workspace = WorkspaceStub()
    cancelled, _, _, _, messages, _, _, _, counts = make_controller(
        cancelled_workspace,
        issues=issue_map,
        selected=("entry-1",),
        confirm_dismissal=False,
    )

    empty.dismiss_selected_ai_issues()
    cancelled.dismiss_selected_ai_issues()

    assert information == [("AI review", "Select entries with AI review issues.")]
    assert counts == [1]
    assert messages == []
    assert cancelled_workspace.dismissed is None


def test_operations_ignore_missing_project_or_busy_state() -> None:
    missing, *missing_results = make_controller(WorkspaceStub(has_project=False), row_count=2)
    busy, *busy_results = make_controller(WorkspaceStub(), busy=True, row_count=2)

    missing.select_all_qa_entries()
    busy.select_all_qa_entries()

    assert all(not result for result in missing_results)
    assert all(not result for result in busy_results)

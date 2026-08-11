from types import SimpleNamespace
from typing import Any, cast

from locaforge.domain.entry import EntryStatus
from locaforge.presentation.translation_navigation_controller import (
    TranslationNavigationController,
)


class WorkspaceStub:
    def __init__(self, entries=(), *, has_project: bool = True) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(entries=entries)


def entry(
    entry_id: str,
    status: EntryStatus = EntryStatus.TRANSLATED,
    *,
    locked: bool = False,
):
    return SimpleNamespace(id=entry_id, status=status, locked=locked)


def make_controller(
    workspace: WorkspaceStub,
    *,
    current_entry: str | None = "entry-1",
    busy: bool = False,
    current_row: int = 1,
    row_count: int = 3,
    issues: frozenset[str] = frozenset(),
    apply_result: bool = True,
):
    selected_rows: list[int] = []
    selected_entries: list[str] = []
    statuses: list[tuple[str, int]] = []
    cleared: list[bool] = []
    applications: list[bool] = []

    def apply() -> bool:
        applications.append(True)
        return apply_result

    controller = TranslationNavigationController(
        cast(Any, workspace),
        current_entry_id=lambda: current_entry,
        is_busy=lambda: busy,
        current_row=lambda: current_row,
        row_count=lambda: row_count,
        select_row=selected_rows.append,
        issue_entry_ids=lambda: issues,
        select_entry=selected_entries.append,
        clear_issues_only=lambda: cleared.append(True),
        show_status=lambda message, timeout: statuses.append((message, timeout)),
        apply_translation=apply,
    )
    return controller, selected_rows, selected_entries, statuses, cleared, applications


def test_selects_adjacent_row_within_table_bounds() -> None:
    controller, rows, _, _, _, _ = make_controller(WorkspaceStub())

    controller.select_relative_entry(1)
    controller.select_relative_entry(-1)

    assert rows == [2, 0]


def test_apply_selects_next_row_only_after_success() -> None:
    successful, successful_rows, _, _, _, successful_calls = make_controller(
        WorkspaceStub(), current_row=0
    )
    failed, failed_rows, _, _, _, failed_calls = make_controller(
        WorkspaceStub(), current_row=0, apply_result=False
    )

    successful.apply_and_select_next()
    failed.apply_and_select_next()

    assert successful_calls == [True]
    assert successful_rows == [1]
    assert failed_calls == [True]
    assert failed_rows == []


def test_issue_navigation_wraps_between_matching_entries() -> None:
    workspace = WorkspaceStub((entry("entry-1"), entry("entry-2"), entry("entry-3")))
    controller, _, selected, statuses, _, _ = make_controller(
        workspace,
        current_entry="entry-3",
        issues=frozenset({"entry-1", "entry-3"}),
    )

    controller.select_relative_issue(1)

    assert selected == ["entry-1"]
    assert statuses == []


def test_issue_navigation_reports_empty_and_ignores_busy_state() -> None:
    workspace = WorkspaceStub((entry("entry-1"),))
    empty, _, selected, statuses, _, _ = make_controller(workspace)
    busy, _, busy_selected, busy_statuses, _, _ = make_controller(
        workspace, busy=True, issues=frozenset({"entry-1"})
    )

    empty.select_relative_issue(1)
    busy.select_relative_issue(1)

    assert selected == []
    assert statuses == [("No validation issues", 3000)]
    assert busy_selected == []
    assert busy_statuses == []


def test_next_actionable_skips_locked_and_translated_entries() -> None:
    workspace = WorkspaceStub(
        (
            entry("entry-1"),
            entry("entry-2", EntryStatus.UNTRANSLATED, locked=True),
            entry("entry-3", EntryStatus.NEEDS_REVIEW),
            entry("entry-4", EntryStatus.ERROR),
        )
    )
    controller, _, selected, statuses, cleared, _ = make_controller(workspace)

    controller.select_next_actionable_entry()

    assert selected == ["entry-3"]
    assert cleared == [True]
    assert statuses == []


def test_next_actionable_reports_when_none_exist() -> None:
    workspace = WorkspaceStub((entry("entry-1"), entry("entry-2", locked=True)))
    controller, _, selected, statuses, cleared, _ = make_controller(workspace)

    controller.select_next_actionable_entry()

    assert selected == []
    assert cleared == []
    assert statuses == [("No actionable entries", 3000)]

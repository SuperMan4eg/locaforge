from collections.abc import Sequence
from typing import Any, cast

from locaforge.presentation.bulk_entry_operations_controller import (
    BulkEntryOperationsController,
)


class WorkspaceStub:
    def __init__(
        self,
        *,
        has_project: bool = True,
        untranslated: tuple[str, ...] = (),
        reviewable: tuple[str, ...] = (),
    ) -> None:
        self.has_project = has_project
        self.untranslated = untranslated
        self.reviewable = reviewable
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def untranslated_entry_ids(self) -> tuple[str, ...]:
        return self.untranslated

    def reviewable_entry_ids(self) -> tuple[str, ...]:
        return self.reviewable

    def set_entries_approval(self, *args: object) -> None:
        self.calls.append(("set_entries_approval", args))

    def set_entries_locked(self, *args: object) -> None:
        self.calls.append(("set_entries_locked", args))


def make_controller(
    workspace: WorkspaceStub,
    *,
    selected: tuple[str, ...] = ("entry-1", "entry-2"),
    current: str | None = "entry-1",
    current_locked: bool = False,
    busy: bool = False,
):
    translations: list[tuple[str, ...]] = []
    reviews: list[tuple[str, ...]] = []
    messages: list[str] = []
    information: list[tuple[str, str]] = []

    def start_translation(entry_ids: Sequence[str]) -> None:
        translations.append(tuple(entry_ids))

    def start_review(entry_ids: Sequence[str]) -> None:
        reviews.append(tuple(entry_ids))

    def run_action(action, message: str) -> bool:
        action()
        messages.append(message)
        return True

    controller = BulkEntryOperationsController(
        cast(Any, workspace),
        selected_entry_ids=lambda: selected,
        current_entry_id=lambda: current,
        current_entry_locked=lambda: current_locked,
        is_busy=lambda: busy,
        start_translation=start_translation,
        start_review=start_review,
        run_action=run_action,
        show_information=lambda title, message: information.append((title, message)),
    )
    return controller, translations, reviews, messages, information


def test_translates_selected_and_all_untranslated_entries() -> None:
    workspace = WorkspaceStub(untranslated=("entry-3", "entry-4"))
    controller, translations, _, _, information = make_controller(workspace)

    controller.translate_selected()
    controller.translate_all_untranslated()

    assert translations == [("entry-1", "entry-2"), ("entry-3", "entry-4")]
    assert information == []


def test_translation_reports_empty_selection_and_empty_eligible_set() -> None:
    workspace = WorkspaceStub()
    controller, translations, _, _, information = make_controller(
        workspace, selected=()
    )

    controller.translate_selected()
    controller.translate_all_untranslated()

    assert translations == []
    assert information == [
        ("Batch translation", "Select one or more rows"),
        ("Batch translation", "There are no untranslated entries to translate."),
    ]


def test_background_operations_ignore_missing_project_or_busy_state() -> None:
    missing, missing_translations, missing_reviews, _, _ = make_controller(
        WorkspaceStub(has_project=False)
    )
    busy, busy_translations, busy_reviews, _, _ = make_controller(
        WorkspaceStub(reviewable=("entry-1",)), busy=True
    )

    missing.translate_selected()
    missing.review_selected()
    busy.translate_all_untranslated()
    busy.review_all()

    assert missing_translations == missing_reviews == []
    assert busy_translations == busy_reviews == []


def test_reviews_selected_and_all_reviewable_entries() -> None:
    workspace = WorkspaceStub(reviewable=("entry-3",))
    controller, _, reviews, _, information = make_controller(workspace)

    controller.review_selected()
    controller.review_all()

    assert reviews == [("entry-1", "entry-2"), ("entry-3",)]
    assert information == []


def test_review_reports_empty_selection_and_empty_reviewable_set() -> None:
    workspace = WorkspaceStub()
    controller, _, reviews, _, information = make_controller(workspace, selected=())

    controller.review_selected()
    controller.review_all()

    assert reviews == []
    assert information == [
        ("AI review", "Select one or more rows"),
        ("AI review", "There are no unlocked Needs review entries"),
    ]


def test_retranslate_current_requires_unlocked_entry() -> None:
    workspace = WorkspaceStub()
    available, translations, _, _, _ = make_controller(workspace)
    missing, missing_translations, _, _, _ = make_controller(workspace, current=None)
    locked, locked_translations, _, _, _ = make_controller(
        workspace, current_locked=True
    )

    available.retranslate_current_entry()
    missing.retranslate_current_entry()
    locked.retranslate_current_entry()

    assert translations == [("entry-1",)]
    assert missing_translations == locked_translations == []


def test_approval_and_lock_operations_delegate_with_messages() -> None:
    workspace = WorkspaceStub()
    controller, _, _, messages, _ = make_controller(workspace)

    controller.approve_selected()
    controller.reopen_selected()
    controller.lock_selected()
    controller.unlock_selected()

    assert workspace.calls == [
        ("set_entries_approval", (("entry-1", "entry-2"), True)),
        ("set_entries_approval", (("entry-1", "entry-2"), False)),
        ("set_entries_locked", (("entry-1", "entry-2"), True)),
        ("set_entries_locked", (("entry-1", "entry-2"), False)),
    ]
    assert messages == [
        "Selected translations approved",
        "Selected translations reopened for review",
        "Selected translations locked",
        "Selected translations unlocked",
    ]


def test_approval_and_lock_report_empty_selection() -> None:
    workspace = WorkspaceStub()
    controller, _, _, messages, information = make_controller(workspace, selected=())

    controller.approve_selected()
    controller.lock_selected()

    assert workspace.calls == []
    assert messages == []
    assert information == [
        ("Review", "Select one or more rows"),
        ("Review", "Select one or more rows"),
    ]

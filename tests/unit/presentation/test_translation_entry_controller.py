from types import SimpleNamespace
from typing import Any, cast

from locaforge.domain.entry import EntryStatus
from locaforge.presentation.translation_entry_controller import TranslationEntryController


def entry(
    entry_id: str,
    source: str = "Hello",
    context: str = "button",
    *,
    locked: bool = False,
    status: EntryStatus = EntryStatus.TRANSLATED,
):
    return SimpleNamespace(
        id=entry_id,
        source=source,
        context=context,
        locked=locked,
        status=status,
    )


class ProjectStub:
    def __init__(self, entries) -> None:
        self.entries = tuple(entries)

    def get_entry(self, entry_id: str):
        return next(item for item in self.entries if item.id == entry_id)


class WorkspaceStub:
    def __init__(self, entries, *, has_project: bool = True) -> None:
        self.has_project = has_project
        self.project = ProjectStub(entries)
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def apply_translation_to_matches(self, *args: object) -> None:
        self.calls.append(("apply_translation_to_matches", args))

    def set_entry_approval(self, *args: object) -> None:
        self.calls.append(("set_entry_approval", args))

    def set_entry_locked(self, *args: object) -> None:
        self.calls.append(("set_entry_locked", args))

    def select_translation_candidate(self, *args: object) -> None:
        self.calls.append(("select_translation_candidate", args))

    def undo_last_translation(self) -> None:
        self.calls.append(("undo_last_translation", ()))

    def redo_last_translation(self) -> None:
        self.calls.append(("redo_last_translation", ()))


def make_controller(
    workspace: WorkspaceStub,
    *,
    current_id: str | None = "entry-1",
    current_locked: bool = False,
    busy: bool = False,
    source_text: str = "Hello",
    translation_text: str = "Привет",
    confirm_matches: bool = True,
):
    translations: list[str] = []
    lock_checks: list[bool] = []
    messages: list[str] = []
    statuses: list[tuple[str, int]] = []
    warnings: list[tuple[str, str]] = []
    confirmations: list[int] = []

    def run_action(action, message: str) -> bool:
        action()
        messages.append(message)
        return True

    controller = TranslationEntryController(
        cast(Any, workspace),
        current_entry_id=lambda: current_id,
        current_entry_locked=lambda: current_locked,
        is_busy=lambda: busy,
        source_text=lambda: source_text,
        translation_text=lambda: translation_text,
        set_translation_text=translations.append,
        set_lock_checked=lock_checks.append,
        run_action=run_action,
        show_status=lambda message, timeout: statuses.append((message, timeout)),
        show_warning=lambda title, message: warnings.append((title, message)),
        confirm_matching_apply=lambda count: (
            confirmations.append(count) or confirm_matches
        ),
    )
    return controller, translations, lock_checks, messages, statuses, warnings, confirmations


def test_copy_source_updates_editor_and_status() -> None:
    workspace = WorkspaceStub((entry("entry-1"),))
    controller, translations, _, _, statuses, _, _ = make_controller(workspace)

    controller.copy_source_to_translation()

    assert translations == ["Hello"]
    assert statuses == [("Source copied to translation editor", 3000)]


def test_copy_source_ignores_missing_locked_or_busy_entry() -> None:
    workspace = WorkspaceStub((entry("entry-1"),))
    controllers = (
        make_controller(workspace, current_id=None),
        make_controller(workspace, current_locked=True),
        make_controller(workspace, busy=True),
    )

    for controller, *_ in controllers:
        controller.copy_source_to_translation()

    assert all(not translations for _, translations, *_ in controllers)


def test_candidate_selection_delegates_with_candidate_message() -> None:
    workspace = WorkspaceStub((entry("entry-1"),))
    model, _, _, model_messages, *_ = make_controller(workspace)
    reviewer, _, _, reviewer_messages, *_ = make_controller(workspace)

    model.select_translation_candidate("model")
    reviewer.select_translation_candidate("reviewer")

    assert workspace.calls == [
        ("select_translation_candidate", ("entry-1", "model")),
        ("select_translation_candidate", ("entry-1", "reviewer")),
    ]
    assert model_messages == ["Model translation selected"]
    assert reviewer_messages == ["Reviewer translation selected"]


def test_candidate_selection_respects_current_entry_guards() -> None:
    workspace = WorkspaceStub((entry("entry-1"),))
    missing, *_ = make_controller(workspace, current_id=None)
    locked, *_ = make_controller(workspace, current_locked=True)
    busy, *_ = make_controller(workspace, busy=True)

    missing.select_translation_candidate("model")
    locked.select_translation_candidate("model")
    busy.select_translation_candidate("model")

    assert workspace.calls == []


def test_undo_and_redo_run_for_idle_open_project() -> None:
    workspace = WorkspaceStub((entry("entry-1"),))
    controller, _, _, messages, *_ = make_controller(workspace)

    controller.undo_last_translation()
    controller.redo_last_translation()

    assert workspace.calls == [
        ("undo_last_translation", ()),
        ("redo_last_translation", ()),
    ]
    assert messages == ["Last operation undone", "Last operation redone"]


def test_undo_and_redo_ignore_missing_project_or_busy_state() -> None:
    missing_workspace = WorkspaceStub((entry("entry-1"),), has_project=False)
    missing, *_ = make_controller(missing_workspace)
    busy_workspace = WorkspaceStub((entry("entry-1"),))
    busy, *_ = make_controller(busy_workspace, busy=True)

    missing.undo_last_translation()
    missing.redo_last_translation()
    busy.undo_last_translation()
    busy.redo_last_translation()

    assert missing_workspace.calls == []
    assert busy_workspace.calls == []


def test_empty_translation_warns_without_matching_lookup() -> None:
    workspace = WorkspaceStub((entry("entry-1"),))
    controller, _, _, _, _, warnings, confirmations = make_controller(
        workspace, translation_text="  "
    )

    controller.apply_translation_to_matches()

    assert warnings == [
        (
            "Apply to matching source",
            "Enter a non-empty translation before applying it to matching entries.",
        )
    ]
    assert confirmations == []
    assert workspace.calls == []


def test_apply_to_matches_counts_only_unlocked_same_context_entries() -> None:
    workspace = WorkspaceStub(
        (
            entry("entry-1"),
            entry("entry-2"),
            entry("entry-3", locked=True),
            entry("entry-4", context="menu"),
            entry("entry-5", source="Other"),
        )
    )
    controller, _, _, messages, _, _, confirmations = make_controller(workspace)

    controller.apply_translation_to_matches()

    assert confirmations == [2]
    assert workspace.calls == [
        ("apply_translation_to_matches", ("entry-1", "Привет"))
    ]
    assert messages == ["Translation applied to 2 entries"]


def test_declined_or_single_match_does_not_apply() -> None:
    matching_workspace = WorkspaceStub((entry("entry-1"), entry("entry-2")))
    declined, *_, confirmations = make_controller(
        matching_workspace, confirm_matches=False
    )
    single_workspace = WorkspaceStub((entry("entry-1"),))
    single, *_ = make_controller(single_workspace)

    declined.apply_translation_to_matches()
    single.apply_translation_to_matches()

    assert confirmations == [2]
    assert matching_workspace.calls == []
    assert single_workspace.calls == []


def test_approval_toggles_from_current_status() -> None:
    workspace = WorkspaceStub(
        (
            entry("entry-1", status=EntryStatus.TRANSLATED),
            entry("entry-2", status=EntryStatus.APPROVED),
        )
    )
    approve, _, _, approve_messages, *_ = make_controller(workspace)
    reopen, _, _, reopen_messages, *_ = make_controller(
        workspace, current_id="entry-2"
    )

    approve.toggle_entry_approval()
    reopen.toggle_entry_approval()

    assert workspace.calls == [
        ("set_entry_approval", ("entry-1", True)),
        ("set_entry_approval", ("entry-2", False)),
    ]
    assert approve_messages == ["Translation approved"]
    assert reopen_messages == ["Translation reopened for review"]


def test_lock_operation_resets_button_without_current_entry() -> None:
    workspace = WorkspaceStub((entry("entry-1"),))
    missing, _, checks, messages, *_ = make_controller(workspace, current_id=None)
    present, _, _, present_messages, *_ = make_controller(workspace)

    missing.set_entry_locked(True)
    present.set_entry_locked(False)

    assert checks == [False]
    assert messages == []
    assert workspace.calls == [("set_entry_locked", ("entry-1", False))]
    assert present_messages == ["Translation unlocked"]

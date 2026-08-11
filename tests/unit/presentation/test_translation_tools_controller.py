from typing import Any, cast

from locaforge.presentation.translation_tools_controller import TranslationToolsController


class WorkspaceStub:
    def __init__(self, *, has_project: bool = True) -> None:
        self.has_project = has_project
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def replace_translations(self, *args: object) -> None:
        self.calls.append(("replace_translations", args))

    def dismiss_ai_review_issue(self, *args: object) -> None:
        self.calls.append(("dismiss_ai_review_issue", args))


def make_controller(
    workspace: WorkspaceStub,
    *,
    current_entry: str | None = "entry-1",
    busy: bool = False,
    replacement: tuple[str, str] | None = ("old", "new"),
    confirm_replacement: bool = True,
    cancel_translation: bool = False,
    cancel_review: bool = False,
):
    validations: list[bool] = []
    replacement_requests: list[bool] = []
    confirmations: list[bool] = []
    messages: list[str] = []
    disabled: list[bool] = []
    statuses: list[str] = []
    translation_cancels: list[bool] = []
    review_cancels: list[bool] = []

    def run_action(action, message: str) -> bool:
        action()
        messages.append(message)
        return True

    def ask_replacement() -> tuple[str, str] | None:
        replacement_requests.append(True)
        return replacement

    def confirm() -> bool:
        confirmations.append(True)
        return confirm_replacement

    def cancel_translation_worker() -> bool:
        translation_cancels.append(True)
        return cancel_translation

    def cancel_review_worker() -> bool:
        review_cancels.append(True)
        return cancel_review

    controller = TranslationToolsController(
        cast(Any, workspace),
        current_entry_id=lambda: current_entry,
        is_busy=lambda: busy,
        start_validation=lambda: validations.append(True),
        ask_replacement=ask_replacement,
        confirm_replacement=confirm,
        run_action=run_action,
        cancel_translation=cancel_translation_worker,
        cancel_review=cancel_review_worker,
        disable_cancel=lambda: disabled.append(True),
        show_status=statuses.append,
    )
    return (
        controller,
        validations,
        replacement_requests,
        confirmations,
        messages,
        disabled,
        statuses,
        translation_cancels,
        review_cancels,
    )


def test_validation_starts_only_for_idle_open_project() -> None:
    active, validations, *_ = make_controller(WorkspaceStub())
    missing, missing_validations, *_ = make_controller(WorkspaceStub(has_project=False))
    busy, busy_validations, *_ = make_controller(WorkspaceStub(), busy=True)

    active.validate_project()
    missing.validate_project()
    busy.validate_project()

    assert validations == [True]
    assert missing_validations == busy_validations == []


def test_replace_collects_values_confirms_and_runs_action() -> None:
    workspace = WorkspaceStub()
    controller, _, requests, confirmations, messages, *_ = make_controller(workspace)

    controller.replace_translations()

    assert requests == [True]
    assert confirmations == [True]
    assert workspace.calls == [("replace_translations", ("old", "new"))]
    assert messages == ["Translations replaced"]


def test_replace_stops_on_cancelled_values_or_confirmation() -> None:
    workspace = WorkspaceStub()
    no_values, _, _, no_value_confirmations, *_ = make_controller(
        workspace, replacement=None
    )
    declined, _, _, declined_confirmations, *_ = make_controller(
        workspace, confirm_replacement=False
    )

    no_values.replace_translations()
    declined.replace_translations()

    assert no_value_confirmations == []
    assert declined_confirmations == [True]
    assert workspace.calls == []


def test_dismiss_current_issue_requires_entry_and_runs_action() -> None:
    workspace = WorkspaceStub()
    present, *present_results = make_controller(workspace)
    missing, *_ = make_controller(workspace, current_entry=None)

    present.dismiss_current_ai_review_issue()
    missing.dismiss_current_ai_review_issue()

    assert workspace.calls == [("dismiss_ai_review_issue", ("entry-1",))]
    assert present_results[3] == ["AI review issue dismissed"]


def test_cancel_prefers_translation_worker_and_disables_button() -> None:
    controller, *results = make_controller(
        WorkspaceStub(), cancel_translation=True, cancel_review=True
    )

    controller.cancel_operation()

    assert results[6] == [True]
    assert results[7] == []
    assert results[4] == [True]
    assert results[5] == [
        "Cancelling translation after the current Ollama request..."
    ]


def test_cancel_falls_back_to_review_or_does_nothing() -> None:
    review, *review_results = make_controller(WorkspaceStub(), cancel_review=True)
    idle, *idle_results = make_controller(WorkspaceStub())

    review.cancel_operation()
    idle.cancel_operation()

    assert review_results[6] == [True]
    assert review_results[7] == [True]
    assert review_results[4] == [True]
    assert review_results[5] == [
        "Cancelling AI review after the current Ollama request..."
    ]
    assert idle_results[4] == []
    assert idle_results[5] == []

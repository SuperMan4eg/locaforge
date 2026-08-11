from types import SimpleNamespace
from typing import Any, cast

import pytest

from locaforge.presentation.window_close_controller import (
    UnsavedChangesDecision,
    WindowCloseController,
)


class WorkspaceStub:
    def __init__(
        self,
        *,
        has_project: bool = True,
        dirty: bool = True,
        save_error: Exception | None = None,
    ) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(dirty=dirty)
        self.save_error = save_error
        self.save_calls = 0

    def save(self) -> None:
        self.save_calls += 1
        if self.save_error is not None:
            raise self.save_error


def make_controller(
    workspace: WorkspaceStub,
    *,
    decision: UnsavedChangesDecision = UnsavedChangesDecision.SAVE,
    translation_running: bool = False,
    review_running: bool = False,
    validation_running: bool = False,
    model_pull_running: bool = False,
):
    decisions: list[bool] = []
    autosave_cancels: list[bool] = []
    waits: list[bool] = []
    layouts: list[bool] = []
    detaches: list[bool] = []
    warnings: list[tuple[str, str]] = []
    errors: list[str] = []

    def ask() -> UnsavedChangesDecision:
        decisions.append(True)
        return decision

    controller = WindowCloseController(
        cast(Any, workspace),
        translation_running=lambda: translation_running,
        review_running=lambda: review_running,
        validation_running=lambda: validation_running,
        model_pull_running=lambda: model_pull_running,
        ask_unsaved_changes=ask,
        cancel_autosave=lambda: autosave_cancels.append(True),
        wait_for_autosave=lambda: waits.append(True),
        persist_layout=lambda: layouts.append(True),
        detach_log_viewer=lambda: detaches.append(True),
        show_warning=lambda title, message: warnings.append((title, message)),
        show_save_error=errors.append,
    )
    return (
        controller,
        decisions,
        autosave_cancels,
        waits,
        layouts,
        detaches,
        warnings,
        errors,
    )


def test_clean_or_missing_project_needs_no_confirmation() -> None:
    clean, clean_decisions, *_ = make_controller(WorkspaceStub(dirty=False))
    missing, missing_decisions, *_ = make_controller(WorkspaceStub(has_project=False))

    assert clean.confirm_unsaved_changes() is True
    assert missing.confirm_unsaved_changes() is True

    assert clean_decisions == missing_decisions == []


def test_save_persists_project_and_cancels_autosave() -> None:
    workspace = WorkspaceStub()
    controller, decisions, cancels, *_ = make_controller(workspace)

    assert controller.confirm_unsaved_changes() is True

    assert decisions == [True]
    assert workspace.save_calls == 1
    assert cancels == [True]


def test_discard_cancels_autosave_without_saving() -> None:
    workspace = WorkspaceStub()
    controller, _, cancels, *_ = make_controller(
        workspace, decision=UnsavedChangesDecision.DISCARD
    )

    assert controller.confirm_unsaved_changes() is True

    assert workspace.save_calls == 0
    assert cancels == [True]


def test_cancel_keeps_project_and_autosave_untouched() -> None:
    workspace = WorkspaceStub()
    controller, _, cancels, *_ = make_controller(
        workspace, decision=UnsavedChangesDecision.CANCEL
    )

    assert controller.confirm_unsaved_changes() is False

    assert workspace.save_calls == 0
    assert cancels == []


def test_save_failure_reports_error_and_blocks_action() -> None:
    workspace = WorkspaceStub(save_error=OSError("disk full"))
    controller, _, cancels, *_, errors = make_controller(workspace)

    assert controller.confirm_unsaved_changes() is False

    assert errors == ["disk full"]
    assert cancels == []


@pytest.mark.parametrize(
    ("running", "title"),
    [
        ("translation_running", "Translation in progress"),
        ("review_running", "AI review in progress"),
        ("validation_running", "Validation in progress"),
        ("model_pull_running", "Model download in progress"),
    ],
)
def test_running_operation_blocks_close_before_unsaved_prompt(
    running: str, title: str
) -> None:
    workspace = WorkspaceStub()
    controller, decisions, _, waits, layouts, detaches, warnings, _ = make_controller(
        workspace, **{running: True}
    )

    assert controller.request_close() is False

    assert decisions == []
    assert warnings[0][0] == title
    assert waits == layouts == detaches == []


def test_successful_close_waits_persists_and_detaches_in_order() -> None:
    workspace = WorkspaceStub(dirty=False)
    events: list[str] = []
    controller = WindowCloseController(
        cast(Any, workspace),
        translation_running=lambda: False,
        review_running=lambda: False,
        validation_running=lambda: False,
        model_pull_running=lambda: False,
        ask_unsaved_changes=lambda: UnsavedChangesDecision.CANCEL,
        cancel_autosave=lambda: events.append("cancel"),
        wait_for_autosave=lambda: events.append("wait"),
        persist_layout=lambda: events.append("layout"),
        detach_log_viewer=lambda: events.append("detach"),
        show_warning=lambda _title, _message: None,
        show_save_error=lambda _message: None,
    )

    assert controller.request_close() is True

    assert events == ["wait", "layout", "detach"]

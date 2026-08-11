from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from locaforge.presentation.application_settings import ApplicationSettings
from locaforge.presentation.autosave_policy_controller import AutosavePolicyController


class WorkspaceStub:
    def __init__(
        self,
        *,
        has_project: bool = True,
        dirty: bool = True,
        container_path: Path | None = Path("project.lfproj"),
    ) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(dirty=dirty)
        self.session = SimpleNamespace(container_path=container_path)
        self.refresh_calls = 0

    def refresh_after_autosave(self) -> None:
        self.refresh_calls += 1


def make_controller(
    workspace: WorkspaceStub,
    *,
    autosave_enabled: bool = True,
):
    schedules: list[bool] = []
    cancellations: list[bool] = []
    refreshes: list[bool] = []
    statuses: list[tuple[str, int]] = []
    failures: list[str] = []
    controller = AutosavePolicyController(
        cast(Any, workspace),
        application_settings=lambda: ApplicationSettings(
            autosave_enabled=autosave_enabled
        ),
        schedule=lambda: schedules.append(True),
        cancel=lambda: cancellations.append(True),
        refresh_project=lambda: refreshes.append(True),
        show_status=lambda message, timeout: statuses.append((message, timeout)),
        show_failure=failures.append,
    )
    return controller, schedules, cancellations, refreshes, statuses, failures


def test_sync_schedules_for_dirty_saved_project_when_enabled() -> None:
    controller, schedules, cancellations, *_ = make_controller(WorkspaceStub())

    controller.sync()

    assert schedules == [True]
    assert cancellations == []


@pytest.mark.parametrize(
    "workspace,enabled",
    [
        (WorkspaceStub(), False),
        (WorkspaceStub(has_project=False), True),
        (WorkspaceStub(dirty=False), True),
        (WorkspaceStub(container_path=None), True),
    ],
)
def test_sync_cancels_when_any_eligibility_condition_fails(
    workspace: WorkspaceStub, enabled: bool
) -> None:
    controller, schedules, cancellations, *_ = make_controller(
        workspace, autosave_enabled=enabled
    )

    controller.sync()

    assert schedules == []
    assert cancellations == [True]


def test_success_refreshes_workspace_then_ui_and_reports_status() -> None:
    workspace = WorkspaceStub()
    events: list[str] = []
    controller = AutosavePolicyController(
        cast(Any, workspace),
        application_settings=ApplicationSettings,
        schedule=lambda: None,
        cancel=lambda: None,
        refresh_project=lambda: events.append("ui"),
        show_status=lambda message, timeout: events.append(f"{message}:{timeout}"),
        show_failure=lambda _message: None,
    )
    original_refresh = workspace.refresh_after_autosave

    def refresh_workspace() -> None:
        events.append("workspace")
        original_refresh()

    workspace.refresh_after_autosave = refresh_workspace

    controller.succeeded()

    assert workspace.refresh_calls == 1
    assert events == ["workspace", "ui", "Project autosaved:3000"]


def test_failure_is_forwarded_without_refresh() -> None:
    workspace = WorkspaceStub()
    controller, _, _, refreshes, statuses, failures = make_controller(workspace)

    controller.failed("disk full")

    assert failures == ["disk full"]
    assert workspace.refresh_calls == 0
    assert refreshes == []
    assert statuses == []

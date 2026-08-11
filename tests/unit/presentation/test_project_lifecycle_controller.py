from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from locaforge.presentation.project_lifecycle_controller import ProjectLifecycleController


class WorkspaceStub:
    def __init__(
        self,
        *,
        has_project: bool = True,
        container_path: Path | None = Path("current.lfproj"),
        open_error: Exception | None = None,
        backup_path: Path = Path("missing-backup"),
    ) -> None:
        self.has_project = has_project
        self.session = SimpleNamespace(container_path=container_path)
        self.open_error = open_error
        self._backup_path = backup_path
        self.opened: list[Path] = []

    def open(self, path: Path) -> None:
        self.opened.append(path)
        if self.open_error is not None:
            raise self.open_error

    def backup_path(self, _path: Path) -> Path:
        return self._backup_path


class ProjectIoStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str) -> Callable[..., bool]:
        def record(*args: object) -> bool:
            self.calls.append((name, args))
            return True

        return record


def make_controller(
    workspace: WorkspaceStub,
    project_io: ProjectIoStub,
    *,
    open_path: Path | None = Path("project.lfproj"),
    save_path: Path | None = Path("saved.lfproj"),
    confirm_unsaved: bool = True,
    confirm_recovery: bool = True,
):
    recoveries: list[tuple[Exception, Path]] = []
    errors: list[str] = []
    opened: list[bool] = []
    controller = ProjectLifecycleController(
        cast(Any, workspace),
        cast(Any, project_io),
        choose_open_path=lambda: open_path,
        choose_save_path=lambda: save_path,
        confirm_unsaved_changes=lambda: confirm_unsaved,
        confirm_recovery=lambda error, backup: (
            recoveries.append((error, backup)) or confirm_recovery
        ),
        show_open_error=errors.append,
        project_opened=lambda: opened.append(True),
    )
    return controller, recoveries, errors, opened


def test_successful_open_notifies_project_opened() -> None:
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    controller, recoveries, errors, opened = make_controller(workspace, project_io)

    controller.open_project()

    assert workspace.opened == [Path("project.lfproj")]
    assert opened == [True]
    assert recoveries == []
    assert errors == []
    assert project_io.calls == []


def test_cancelled_selection_or_unsaved_confirmation_stops_open() -> None:
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    no_path, _, _, _ = make_controller(workspace, project_io, open_path=None)
    declined, _, _, _ = make_controller(workspace, project_io, confirm_unsaved=False)

    no_path.open_project()
    declined.open_project()

    assert workspace.opened == []


def test_failed_open_without_backup_reports_error(tmp_path: Path) -> None:
    error = ValueError("broken project")
    workspace = WorkspaceStub(open_error=error, backup_path=tmp_path / "missing.bak")
    project_io = ProjectIoStub()
    controller, recoveries, errors, opened = make_controller(workspace, project_io)

    controller.open_project()

    assert errors == ["broken project"]
    assert recoveries == []
    assert opened == []


def test_failed_open_can_recover_from_existing_backup(tmp_path: Path) -> None:
    backup = tmp_path / "project.lfproj.bak"
    backup.write_text("backup", encoding="utf-8")
    error = ValueError("broken project")
    workspace = WorkspaceStub(open_error=error, backup_path=backup)
    project_io = ProjectIoStub()
    controller, recoveries, errors, opened = make_controller(workspace, project_io)

    controller.open_project()

    assert recoveries == [(error, backup)]
    assert project_io.calls == [("open_backup", (Path("project.lfproj"),))]
    assert errors == []
    assert opened == []


def test_save_uses_current_path_or_save_as_when_unsaved() -> None:
    project_io = ProjectIoStub()
    saved_workspace = WorkspaceStub()
    saved_controller, _, _, _ = make_controller(saved_workspace, project_io)
    unsaved_workspace = WorkspaceStub(container_path=None)
    unsaved_controller, _, _, _ = make_controller(unsaved_workspace, project_io)

    saved_controller.save_project()
    unsaved_controller.save_project()

    assert project_io.calls == [
        ("save", ()),
        ("save", (Path("saved.lfproj"),)),
    ]


def test_save_as_requires_project_and_destination() -> None:
    project_io = ProjectIoStub()
    no_project, _, _, _ = make_controller(
        WorkspaceStub(has_project=False), project_io
    )
    no_destination, _, _, _ = make_controller(
        WorkspaceStub(), project_io, save_path=None
    )

    no_project.save_project_as()
    no_destination.save_project_as()

    assert project_io.calls == []

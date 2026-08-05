from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from locaforge.presentation.project_io_controller import ProjectIoController


class WorkspaceStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str) -> Callable[..., object]:
        def record(*args: object) -> object:
            self.calls.append((name, args))
            return object()

        return record


def make_controller(
    workspace: WorkspaceStub, *, succeeds: bool = True
) -> tuple[ProjectIoController, list[str], list[str]]:
    messages: list[str] = []
    changes: list[str] = []

    def run(action: Callable[[], object], message: str) -> bool:
        messages.append(message)
        action()
        return succeeds

    controller = ProjectIoController(
        cast(Any, workspace), run, lambda: changes.append("changed")
    )
    return controller, messages, changes


def test_save_as_normalizes_project_suffix_and_notifies() -> None:
    workspace = WorkspaceStub()
    controller, messages, changes = make_controller(workspace)

    assert controller.save(Path("release")) is True

    assert workspace.calls == [("save", (Path("release.lfproj"),))]
    assert messages == ["Project saved"]
    assert changes == ["changed"]


def test_failed_project_action_does_not_notify() -> None:
    workspace = WorkspaceStub()
    controller, _, changes = make_controller(workspace, succeeds=False)

    assert controller.open(Path("broken.lfproj")) is False

    assert changes == []


def test_csv_export_preserves_tsv_and_defaults_unknown_suffix_to_csv() -> None:
    workspace = WorkspaceStub()
    controller, messages, changes = make_controller(workspace)

    controller.export_csv(Path("translations.tsv"))
    controller.export_csv(Path("translations.txt"))

    assert workspace.calls == [
        ("export_csv", (Path("translations.tsv"),)),
        ("export_csv", (Path("translations.csv"),)),
    ]
    assert messages == ["CSV/TSV exported", "CSV/TSV exported"]
    assert changes == []


def test_json_project_creation_passes_mapping_and_normalized_destination() -> None:
    workspace = WorkspaceStub()
    controller, _, changes = make_controller(workspace)
    mapping = object()

    controller.create_from_json(
        Path("source.json"), Path("project.tmp"), "en", "ru", cast(Any, mapping)
    )

    assert workspace.calls == [
        (
            "create_from_json",
            (Path("source.json"), Path("project.lfproj"), "en", "ru", mapping),
        )
    ]
    assert changes == ["changed"]

from pathlib import Path
from typing import Any, cast

import pytest

from locaforge.application.dto.project import ExportPreflight
from locaforge.presentation.project_export_controller import ProjectExportController


class WorkspaceStub:
    def __init__(self, *, has_project: bool = True) -> None:
        self.has_project = has_project
        self.preflight = ExportPreflight(2, 1)
        self.preflight_calls = 0

    def export_preflight(self) -> ExportPreflight:
        self.preflight_calls += 1
        return self.preflight


class ProjectIoStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str):
        def record(*args: object) -> bool:
            self.calls.append((name, args))
            return True

        return record


def make_controller(
    workspace: WorkspaceStub,
    project_io: ProjectIoStub,
    *,
    selected: tuple[str, ...] = ("document-1",),
    file_destination: Path | None = Path("translation.out"),
    directory_destination: Path | None = Path("exports"),
    warnings_enabled: bool = False,
    confirm: bool = True,
):
    save_requests: list[tuple[str, str]] = []
    directory_requests: list[str] = []
    confirmations: list[tuple[ExportPreflight, str]] = []
    no_selection: list[bool] = []

    def choose_file(title: str, file_filter: str) -> Path | None:
        save_requests.append((title, file_filter))
        return file_destination

    def choose_directory(title: str) -> Path | None:
        directory_requests.append(title)
        return directory_destination

    def confirm_warnings(preflight: ExportPreflight, effect: str) -> bool:
        confirmations.append((preflight, effect))
        return confirm

    controller = ProjectExportController(
        cast(Any, workspace),
        cast(Any, project_io),
        selected_document_ids=lambda: selected,
        choose_save_file=choose_file,
        choose_directory=choose_directory,
        warnings_enabled=lambda: warnings_enabled,
        confirm_warnings=confirm_warnings,
        show_no_selection=lambda: no_selection.append(True),
    )
    return controller, save_requests, directory_requests, confirmations, no_selection


@pytest.mark.parametrize(
    ("method", "export_method", "title", "file_filter"),
    [
        ("export_json", "export_json", "Export translated JSON", "JSON files (*.json)"),
        ("export_po", "export_po", "Export translated PO", "Gettext PO files (*.po)"),
        (
            "export_csv",
            "export_csv",
            "Export translated CSV/TSV",
            "Delimited text files (*.csv *.tsv)",
        ),
        ("export_xml", "export_xml", "Export translated XML", "XML files (*.xml)"),
    ],
)
def test_file_exports_choose_destination_and_delegate(
    method: str, export_method: str, title: str, file_filter: str
) -> None:
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    controller, requests, _, _, _ = make_controller(workspace, project_io)

    getattr(controller, method)()

    assert requests == [(title, file_filter)]
    assert project_io.calls == [(export_method, (Path("translation.out"),))]
    assert workspace.preflight_calls == 0


def test_rejected_warning_stops_before_destination_selection() -> None:
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    controller, requests, _, confirmations, _ = make_controller(
        workspace, project_io, warnings_enabled=True, confirm=False
    )

    controller.export_json()

    assert confirmations == [(workspace.preflight, "will retain source text")]
    assert requests == []
    assert project_io.calls == []


def test_missing_project_or_cancelled_destination_does_not_export() -> None:
    project_io = ProjectIoStub()
    missing_controller, requests, _, _, _ = make_controller(
        WorkspaceStub(has_project=False), project_io
    )
    missing_controller.export_po()

    cancelled_controller, cancelled_requests, _, _, _ = make_controller(
        WorkspaceStub(), project_io, file_destination=None
    )
    cancelled_controller.export_po()

    assert requests == []
    assert len(cancelled_requests) == 1
    assert project_io.calls == []


def test_all_and_selected_document_exports_delegate_to_directory() -> None:
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    controller, _, requests, _, _ = make_controller(
        workspace, project_io, selected=("document-1", "document-2")
    )

    controller.export_all_documents()
    controller.export_selected_documents()

    assert requests == ["Export all project files", "Export selected project files"]
    assert project_io.calls == [
        ("export_all_documents", (Path("exports"),)),
        ("export_documents", (("document-1", "document-2"), Path("exports"))),
    ]


def test_selected_export_reports_empty_selection_without_preflight() -> None:
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    controller, _, requests, _, no_selection = make_controller(
        workspace, project_io, selected=(), warnings_enabled=True
    )

    controller.export_selected_documents()

    assert no_selection == [True]
    assert requests == []
    assert workspace.preflight_calls == 0

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from locaforge.presentation.project_file_import_controller import (
    ProjectFileImportController,
)


class WorkspaceStub:
    def __init__(self, *, has_project: bool = True) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(
            documents=(SimpleNamespace(source_path="existing.po"),)
        )


class ProjectIoStub:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Path, ...], dict[Path, object], object]] = []

    def import_files(self, sources, mappings, document_paths) -> bool:
        self.calls.append((sources, mappings, document_paths))
        return True


def make_controller(
    workspace: WorkspaceStub,
    project_io: ProjectIoStub,
    *,
    files: tuple[Path, ...] = (),
    folder: Path | None = None,
    preview_result: object = "suggested",
    csv_mapping: object | None = object(),
):
    information: list[tuple[str, str]] = []
    previews: list[tuple[tuple[Path, ...], object, tuple[Path, ...]]] = []
    mapping_requests: list[tuple[str, Path]] = []

    def preview(sources, suggested, existing):
        previews.append((sources, suggested, existing))
        return suggested if preview_result == "suggested" else preview_result

    controller = ProjectFileImportController(
        cast(Any, workspace),
        cast(Any, project_io),
        choose_files=lambda: files,
        choose_folder=lambda: folder,
        preview_import=preview,
        ask_json_mapping=lambda path: (
            mapping_requests.append(("json", path)) or cast(Any, "json-mapping")
        ),
        ask_csv_mapping=lambda path: (
            mapping_requests.append(("csv", path)) or cast(Any, csv_mapping)
        ),
        ask_xml_mapping=lambda path: (
            mapping_requests.append(("xml", path)) or cast(Any, "xml-mapping")
        ),
        show_information=lambda title, message: information.append((title, message)),
    )
    return controller, information, previews, mapping_requests


def test_add_files_requires_an_open_project() -> None:
    workspace = WorkspaceStub(has_project=False)
    project_io = ProjectIoStub()
    controller, information, _, _ = make_controller(workspace, project_io)

    controller.add_files()

    assert information == [
        ("Add files", "Create or open a project before adding localization files.")
    ]
    assert project_io.calls == []


def test_add_folder_reports_when_no_supported_files_exist(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not localization", encoding="utf-8")
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    controller, information, _, _ = make_controller(
        workspace, project_io, folder=tmp_path
    )

    controller.add_folder()

    assert information == [
        ("Add files", "No supported JSON, CSV/TSV, PO, or XML files were found.")
    ]
    assert project_io.calls == []


def test_import_paths_previews_collects_mappings_and_delegates(tmp_path: Path) -> None:
    json_path = tmp_path / "a.json"
    csv_path = tmp_path / "nested" / "b.csv"
    po_path = tmp_path / "c.po"
    xml_path = tmp_path / "d.xml"
    csv_path.parent.mkdir()
    for path in (json_path, csv_path, po_path, xml_path):
        path.write_text("content", encoding="utf-8")
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    controller, _, previews, mapping_requests = make_controller(workspace, project_io)

    controller.import_paths((tmp_path,))

    sources, mappings, document_paths = project_io.calls[0]
    assert set(sources) == {path.resolve() for path in (json_path, csv_path, po_path, xml_path)}
    assert {path.suffix for path in mappings} == {".json", ".csv", ".xml"}
    assert set(document_paths.values()) == {"a.json", "nested/b.csv", "c.po", "d.xml"}
    assert previews[0][2] == ("existing.po",)
    assert {kind for kind, _ in mapping_requests} == {"json", "csv", "xml"}


def test_cancelled_preview_or_csv_mapping_stops_import(tmp_path: Path) -> None:
    csv_path = tmp_path / "strings.csv"
    csv_path.write_text("source,target", encoding="utf-8")
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    preview_cancelled, _, _, _ = make_controller(
        workspace, project_io, preview_result=None
    )
    preview_cancelled.import_paths((csv_path,))

    mapping_cancelled, _, _, _ = make_controller(
        workspace, project_io, csv_mapping=None
    )
    mapping_cancelled.import_paths((csv_path,))

    assert project_io.calls == []

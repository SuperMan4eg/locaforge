"""File and folder import orchestration for existing projects."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.application.project_workspace import ImportFieldMapping, ProjectWorkspace
from locaforge.presentation.import_file_selection import (
    collect_import_files,
    project_import_paths,
)
from locaforge.presentation.project_io_controller import ProjectIoController

type PreviewImport = Callable[
    [tuple[Path, ...], dict[Path, str], tuple[str, ...]],
    Mapping[Path, str] | None,
]


class ProjectFileImportController:
    """Collects import inputs and delegates the resulting project mutation."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        project_io: ProjectIoController,
        choose_files: Callable[[], Sequence[Path]],
        choose_folder: Callable[[], Path | None],
        preview_import: PreviewImport,
        ask_json_mapping: Callable[[Path], JsonFieldMapping | None],
        ask_csv_mapping: Callable[[Path], CsvFieldMapping | None],
        ask_xml_mapping: Callable[[Path], XmlFieldMapping | None],
        show_information: Callable[[str, str], None],
    ) -> None:
        self._workspace = workspace
        self._project_io = project_io
        self._choose_files = choose_files
        self._choose_folder = choose_folder
        self._preview_import = preview_import
        self._ask_json_mapping = ask_json_mapping
        self._ask_csv_mapping = ask_csv_mapping
        self._ask_xml_mapping = ask_xml_mapping
        self._show_information = show_information

    def add_files(self) -> None:
        if not self._workspace.has_project:
            self._show_information(
                "Add files",
                "Create or open a project before adding localization files.",
            )
            return
        selected_paths = tuple(self._choose_files())
        if selected_paths:
            self.import_paths(selected_paths)

    def add_folder(self) -> None:
        if not self._workspace.has_project:
            self._show_information(
                "Add folder", "Create or open a project before adding files."
            )
            return
        selected_path = self._choose_folder()
        if selected_path is not None:
            self.import_paths((selected_path,))

    def import_paths(self, selected_paths: tuple[Path, ...]) -> None:
        source_paths = collect_import_files(selected_paths)
        if not source_paths:
            self._show_information(
                "Add files",
                "No supported JSON, CSV/TSV, PO, or XML files were found.",
            )
            return
        suggested_paths = project_import_paths(source_paths, selected_paths)
        existing_paths = tuple(
            document.source_path for document in self._workspace.project.documents
        )
        document_paths = self._preview_import(source_paths, suggested_paths, existing_paths)
        if document_paths is None:
            return
        field_mappings: dict[Path, ImportFieldMapping] = {}
        for source_path in source_paths:
            suffix = source_path.suffix.lower()
            if suffix == ".json":
                field_mappings[source_path] = self._ask_json_mapping(source_path)
            elif suffix in {".csv", ".tsv"}:
                mapping = self._ask_csv_mapping(source_path)
                if mapping is None:
                    return
                field_mappings[source_path] = mapping
            elif suffix == ".xml":
                field_mappings[source_path] = self._ask_xml_mapping(source_path)
        self._project_io.import_files(source_paths, field_mappings, document_paths)

"""Project export orchestration for the desktop UI."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from locaforge.application.dto.project import ExportPreflight
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.project_io_controller import ProjectIoController

type SaveFileChooser = Callable[[str, str], Path | None]
type DirectoryChooser = Callable[[str], Path | None]
type WarningConfirmation = Callable[[ExportPreflight, str], bool]


class ProjectExportController:
    """Coordinates export preflight, destinations, and document selection."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        project_io: ProjectIoController,
        selected_document_ids: Callable[[], Iterable[str]],
        choose_save_file: SaveFileChooser,
        choose_directory: DirectoryChooser,
        warnings_enabled: Callable[[], bool],
        confirm_warnings: WarningConfirmation,
        show_no_selection: Callable[[], None],
    ) -> None:
        self._workspace = workspace
        self._project_io = project_io
        self._selected_document_ids = selected_document_ids
        self._choose_save_file = choose_save_file
        self._choose_directory = choose_directory
        self._warnings_enabled = warnings_enabled
        self._confirm_warnings = confirm_warnings
        self._show_no_selection = show_no_selection

    def export_json(self) -> None:
        self._export_file(
            "Export translated JSON",
            "JSON files (*.json)",
            "will retain source text",
            self._project_io.export_json,
        )

    def export_po(self) -> None:
        self._export_file(
            "Export translated PO",
            "Gettext PO files (*.po)",
            "will be empty",
            self._project_io.export_po,
        )

    def export_csv(self) -> None:
        self._export_file(
            "Export translated CSV/TSV",
            "Delimited text files (*.csv *.tsv)",
            "will be empty",
            self._project_io.export_csv,
        )

    def export_xml(self) -> None:
        self._export_file(
            "Export translated XML",
            "XML files (*.xml)",
            "will retain source text",
            self._project_io.export_xml,
        )

    def export_all_documents(self) -> None:
        if not self._can_export(
            "will retain source text or remain empty, depending on the file format"
        ):
            return
        destination = self._choose_directory("Export all project files")
        if destination is not None:
            self._project_io.export_all_documents(destination)

    def export_selected_documents(self) -> None:
        document_ids = tuple(self._selected_document_ids())
        if not document_ids:
            self._show_no_selection()
            return
        if not self._can_export("will retain their source-format default"):
            return
        destination = self._choose_directory("Export selected project files")
        if destination is not None:
            self._project_io.export_documents(document_ids, destination)

    def _export_file(
        self,
        title: str,
        file_filter: str,
        untranslated_effect: str,
        export: Callable[[Path], bool],
    ) -> None:
        if not self._can_export(untranslated_effect):
            return
        destination = self._choose_save_file(title, file_filter)
        if destination is not None:
            export(destination)

    def _can_export(self, untranslated_effect: str) -> bool:
        if not self._workspace.has_project:
            return False
        if not self._warnings_enabled():
            return True
        preflight = self._workspace.export_preflight()
        return not preflight.has_warnings or self._confirm_warnings(
            preflight, untranslated_effect
        )

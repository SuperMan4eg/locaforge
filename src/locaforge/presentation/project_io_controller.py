"""Project file lifecycle orchestration for the desktop UI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.application.project_workspace import ProjectWorkspace

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


class ProjectIoController:
    """Runs project I/O actions and applies presentation-level path rules."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        run_action: ActionRunner,
        project_changed: Callable[[], None],
    ) -> None:
        self._workspace = workspace
        self._run_action = run_action
        self._project_changed = project_changed

    @staticmethod
    def with_suffix(path: Path, suffix: str, accepted: set[str] | None = None) -> Path:
        accepted_suffixes = accepted or {suffix}
        return path if path.suffix.lower() in accepted_suffixes else path.with_suffix(suffix)

    def create_from_json(
        self,
        source: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: JsonFieldMapping | None,
    ) -> bool:
        return self._run_project_change(
            lambda: self._workspace.create_from_json(
                source,
                self.with_suffix(destination, ".lfproj"),
                source_language,
                target_language,
                field_mapping,
            ),
            "Project created",
        )

    def create_from_po(
        self,
        source: Path,
        destination: Path,
        source_language: str,
        target_language: str,
    ) -> bool:
        return self._run_project_change(
            lambda: self._workspace.create_from_po(
                source,
                self.with_suffix(destination, ".lfproj"),
                source_language,
                target_language,
            ),
            "Project created",
        )

    def create_from_csv(
        self,
        source: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: CsvFieldMapping,
    ) -> bool:
        return self._run_project_change(
            lambda: self._workspace.create_from_csv(
                source,
                self.with_suffix(destination, ".lfproj"),
                source_language,
                target_language,
                field_mapping,
            ),
            "Project created",
        )

    def create_from_xml(
        self,
        source: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: XmlFieldMapping | None,
    ) -> bool:
        return self._run_project_change(
            lambda: self._workspace.create_from_xml(
                source,
                self.with_suffix(destination, ".lfproj"),
                source_language,
                target_language,
                field_mapping,
            ),
            "Project created",
        )

    def open(self, path: Path) -> bool:
        return self._run_project_change(lambda: self._workspace.open(path), "Project opened")

    def save(self, destination: Path | None = None) -> bool:
        action = (
            self._workspace.save
            if destination is None
            else lambda: self._workspace.save(self.with_suffix(destination, ".lfproj"))
        )
        return self._run_project_change(action, "Project saved")

    def export_json(self, destination: Path) -> bool:
        return self._run_action(
            lambda: self._workspace.export_json(self.with_suffix(destination, ".json")),
            "JSON exported",
        )

    def export_po(self, destination: Path) -> bool:
        return self._run_action(
            lambda: self._workspace.export_po(self.with_suffix(destination, ".po")),
            "PO exported",
        )

    def export_csv(self, destination: Path) -> bool:
        return self._run_action(
            lambda: self._workspace.export_csv(
                self.with_suffix(destination, ".csv", {".csv", ".tsv"})
            ),
            "CSV/TSV exported",
        )

    def export_xml(self, destination: Path) -> bool:
        return self._run_action(
            lambda: self._workspace.export_xml(self.with_suffix(destination, ".xml")),
            "XML exported",
        )

    def _run_project_change(self, action: ProjectAction, success_message: str) -> bool:
        succeeded = self._run_action(action, success_message)
        if succeeded:
            self._project_changed()
        return succeeded

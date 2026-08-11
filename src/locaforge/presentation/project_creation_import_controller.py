"""Create-project import orchestration for supported localization formats."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.presentation.project_io_controller import ProjectIoController

type SourceChooser = Callable[[str, str], Path | None]
type ProjectSetup = Callable[[Path, Path, str, str], tuple[str, str] | None]


class ProjectCreationImportController:
    """Coordinates creation of a project from one localization file."""

    def __init__(
        self,
        project_io: ProjectIoController,
        choose_source: SourceChooser,
        choose_destination: Callable[[], Path | None],
        ask_project_setup: ProjectSetup,
        confirm_unsaved_changes: Callable[[], bool],
        ask_json_mapping: Callable[[Path], JsonFieldMapping | None],
        ask_csv_mapping: Callable[[Path], CsvFieldMapping | None],
        ask_xml_mapping: Callable[[Path], XmlFieldMapping | None],
    ) -> None:
        self._project_io = project_io
        self._choose_source = choose_source
        self._choose_destination = choose_destination
        self._ask_project_setup = ask_project_setup
        self._confirm_unsaved_changes = confirm_unsaved_changes
        self._ask_json_mapping = ask_json_mapping
        self._ask_csv_mapping = ask_csv_mapping
        self._ask_xml_mapping = ask_xml_mapping

    def import_json(self) -> None:
        source = self._choose_source("Import JSON", "JSON files (*.json)")
        if source is None:
            return
        mapping = self._ask_json_mapping(source)
        destination = self._choose_destination()
        if destination is None:
            return
        description = (
            "Automatic: every string value is translated and its JSON path is used as the key"
            if mapping is None
            else (
                f"Source: {mapping.source_field}; target: {mapping.target_field}; "
                f"key: {mapping.key_field or 'generated JSON path'}"
            )
        )
        languages = self._prepare(source, destination, "JSON", description)
        if languages is not None:
            self._project_io.create_from_json(source, destination, *languages, mapping)

    def import_po(self) -> None:
        source = self._choose_source("Import PO", "Gettext PO files (*.po)")
        if source is None:
            return
        destination = self._choose_destination()
        if destination is None:
            return
        languages = self._prepare(
            source,
            destination,
            "PO",
            "Gettext msgid is the source, msgstr is the translation, and "
            "comments/context are preserved",
        )
        if languages is not None:
            self._project_io.create_from_po(source, destination, *languages)

    def import_csv(self) -> None:
        source = self._choose_source(
            "Import CSV/TSV", "Delimited text files (*.csv *.tsv);;All files (*)"
        )
        if source is None:
            return
        mapping = self._ask_csv_mapping(source)
        if mapping is None:
            return
        destination = self._choose_destination()
        if destination is None:
            return
        languages = self._prepare(
            source,
            destination,
            "CSV/TSV",
            f"Source: {mapping.source_field}; target: {mapping.target_field}; "
            f"key: {mapping.key_field or 'generated row number'}",
        )
        if languages is not None:
            self._project_io.create_from_csv(source, destination, *languages, mapping)

    def import_xml(self) -> None:
        source = self._choose_source("Import XML", "XML files (*.xml)")
        if source is None:
            return
        mapping = self._ask_xml_mapping(source)
        destination = self._choose_destination()
        if destination is None:
            return
        description = (
            "Element text nodes; XML structure, comments, and non-translatable values are preserved"
            if mapping is None
            else "Element text nodes and attributes: " + ", ".join(mapping.attribute_names)
        )
        languages = self._prepare(source, destination, "XML", description)
        if languages is not None:
            self._project_io.create_from_xml(source, destination, *languages, mapping)

    def _prepare(
        self, source: Path, destination: Path, source_format: str, description: str
    ) -> tuple[str, str] | None:
        languages = self._ask_project_setup(source, destination, source_format, description)
        if languages is None or not self._confirm_unsaved_changes():
            return None
        return languages

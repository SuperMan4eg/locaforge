"""Interfaces for localization CSV import and export."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from locaforge.domain.project import Project


@dataclass(frozen=True, slots=True)
class CsvFieldMapping:
    source_field: str
    target_field: str
    key_field: str | None = None
    import_existing_translations: bool = True


class CsvImporter(Protocol):
    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
        field_mapping: CsvFieldMapping,
    ) -> Project: ...

    def inspect_fields(self, path: Path) -> tuple[str, ...]: ...


class CsvExporter(Protocol):
    def export_file(self, project: Project, destination: Path) -> None: ...

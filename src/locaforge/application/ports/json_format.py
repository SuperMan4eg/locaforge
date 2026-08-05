"""Interfaces for lossless JSON import and export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from locaforge.domain.project import Project


@dataclass(frozen=True, slots=True)
class JsonFieldMapping:
    source_field: str
    target_field: str
    key_field: str | None = None
    import_existing_translations: bool = True


class JsonImporter(Protocol):
    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
        field_mapping: JsonFieldMapping | None = None,
    ) -> Project: ...

    def inspect_fields(self, path: Path) -> tuple[str, ...]: ...


class JsonExporter(Protocol):
    def export_file(self, project: Project, destination: Path) -> None: ...

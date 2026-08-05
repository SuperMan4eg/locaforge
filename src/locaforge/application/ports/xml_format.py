"""Interfaces for lossless-enough XML import and export."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from locaforge.domain.project import Project


@dataclass(frozen=True, slots=True)
class XmlFieldMapping:
    attribute_names: tuple[str, ...] = ()


class XmlImporter(Protocol):
    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
        field_mapping: XmlFieldMapping | None = None,
    ) -> Project: ...

    def inspect_attribute_names(self, path: Path) -> tuple[str, ...]: ...


class XmlExporter(Protocol):
    def export_file(self, project: Project, destination: Path) -> None: ...

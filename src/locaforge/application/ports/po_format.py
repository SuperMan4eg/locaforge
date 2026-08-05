"""Interfaces for GNU gettext PO import and export."""

from pathlib import Path
from typing import Protocol

from locaforge.domain.project import Project


class PoImporter(Protocol):
    def import_file(
        self, path: Path, source_language: str, target_language: str
    ) -> Project: ...


class PoExporter(Protocol):
    def export_file(self, project: Project, destination: Path) -> None: ...

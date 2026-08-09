"""Imported localization document owned by a project."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProjectDocument:
    """A source file and the format-specific data required for round-trip export."""

    id: str
    name: str
    source_path: str
    source_format: str
    source_document: object

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ProjectDocument.id must not be empty")
        if not self.name.strip():
            raise ValueError("ProjectDocument.name must not be empty")
        if not self.source_path:
            raise ValueError("ProjectDocument.source_path must not be empty")
        if not self.source_format:
            raise ValueError("ProjectDocument.source_format must not be empty")

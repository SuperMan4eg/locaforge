"""Project entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.settings import ModelSettings


@dataclass(slots=True)
class Project:
    """The aggregate root for a single imported localization project."""

    id: str
    name: str
    source_language: str
    target_language: str
    entries: list[TranslationEntry] = field(default_factory=list)
    source_document: object | None = None
    model_settings: ModelSettings = field(default_factory=ModelSettings)
    dirty: bool = False
    documents: list[ProjectDocument] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Project.id must not be empty")
        if not self.name.strip():
            raise ValueError("Project.name must not be empty")
        if not self.source_language or not self.target_language:
            raise ValueError("Project languages must not be empty")
        if not self.documents:
            self.documents.append(
                ProjectDocument(
                    id=f"{self.id}:document:0",
                    name=self.name,
                    source_path=self.name,
                    source_format="legacy",
                    source_document=self.source_document,
                )
            )
        document_ids = {document.id for document in self.documents}
        if len(document_ids) != len(self.documents):
            raise ValueError("Project document ids must be unique")
        for entry in self.entries:
            if entry.document_id is None:
                entry.document_id = self.documents[0].id
            elif entry.document_id not in document_ids:
                raise ValueError(f"Entry {entry.id!r} belongs to an unknown document")
        self.source_document = self.documents[0].source_document

    def configure_single_document(self, source_path: Path, source_format: str) -> None:
        """Attach imported-file metadata while retaining the legacy export surface."""
        document = ProjectDocument(
            id=f"{self.id}:document:0",
            name=source_path.name,
            source_path=source_path.name,
            source_format=source_format,
            source_document=self.source_document,
        )
        self.documents = [document]
        for entry in self.entries:
            entry.document_id = document.id

    def get_document(self, document_id: str) -> ProjectDocument:
        for document in self.documents:
            if document.id == document_id:
                return document
        raise KeyError(f"Document {document_id!r} was not found")

    def add_entry(self, entry: TranslationEntry) -> None:
        if any(existing.id == entry.id for existing in self.entries):
            raise ValueError(f"An entry with id {entry.id!r} already exists")
        if entry.document_id is None:
            entry.document_id = self.documents[0].id
        elif not any(document.id == entry.document_id for document in self.documents):
            raise ValueError(f"Entry {entry.id!r} belongs to an unknown document")
        self.entries.append(entry)
        self.dirty = True

    def get_entry(self, entry_id: str) -> TranslationEntry:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        raise KeyError(f"Entry {entry_id!r} was not found")

    def set_entry_translation(self, entry_id: str, translation: str | None) -> TranslationEntry:
        entry = self.get_entry(entry_id)
        entry.set_translation(translation)
        self.dirty = True
        return entry

    def mark_saved(self) -> None:
        self.dirty = False

    def update_model_settings(self, settings: ModelSettings) -> None:
        self.model_settings = settings
        self.dirty = True

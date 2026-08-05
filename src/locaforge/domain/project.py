"""Project entity."""

from __future__ import annotations

from dataclasses import dataclass, field

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

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Project.id must not be empty")
        if not self.name.strip():
            raise ValueError("Project.name must not be empty")
        if not self.source_language or not self.target_language:
            raise ValueError("Project languages must not be empty")

    def add_entry(self, entry: TranslationEntry) -> None:
        if any(existing.id == entry.id for existing in self.entries):
            raise ValueError(f"An entry with id {entry.id!r} already exists")
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

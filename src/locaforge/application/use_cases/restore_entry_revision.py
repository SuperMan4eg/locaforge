"""Restore a previous translation revision."""

from __future__ import annotations

from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.domain.entry import TranslationEntry


class RestoreEntryRevision:
    def __init__(
        self,
        project_repository: ProjectRepository,
        translation_memory: TranslationMemoryStore | None = None,
        glossary: GlossaryStore | None = None,
    ) -> None:
        self._project_repository = project_repository
        self._translation_memory = translation_memory
        self._glossary = glossary

    def execute(
        self,
        project_id: str,
        entry_id: str,
        revision_id: int,
    ) -> TranslationEntry:
        entry = self._project_repository.get_entry(project_id, entry_id)
        if entry.locked:
            raise ValueError("Unlock the entry before restoring its translation history")
        revision = self._project_repository.get_entry_revision(
            project_id, entry_id, revision_id
        )
        return EditTranslation(
            self._project_repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        ).execute(project_id, entry_id, revision.translation)

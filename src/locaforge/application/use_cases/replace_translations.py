"""Bulk replacement workflow for existing translations."""

from __future__ import annotations

from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.use_cases.edit_translation import EditTranslation


class ReplaceTranslations:
    """Replace text in editable translations while preserving normal edit rules."""

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
        search_text: str,
        replacement_text: str,
    ) -> tuple[str, ...]:
        if not search_text:
            raise ValueError("Text to find must not be empty")

        project = self._project_repository.get(project_id)
        entry_ids = tuple(
            entry.id
            for entry in project.entries
            if not entry.locked
            and entry.translation is not None
            and search_text in entry.translation
        )
        editor = EditTranslation(
            self._project_repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        )
        for entry_id in entry_ids:
            entry = self._project_repository.get_entry(project_id, entry_id)
            if entry.translation is not None:
                editor.execute(
                    project_id,
                    entry_id,
                    entry.translation.replace(search_text, replacement_text),
                )
        return entry_ids

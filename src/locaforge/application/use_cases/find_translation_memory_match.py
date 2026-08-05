"""Exact translation memory lookup workflow."""

from __future__ import annotations

from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.domain.translation_memory import TranslationMemoryRecord


class FindTranslationMemoryMatch:
    def __init__(
        self,
        project_repository: ProjectRepository,
        translation_memory: TranslationMemoryStore,
    ) -> None:
        self._project_repository = project_repository
        self._translation_memory = translation_memory

    def execute(self, project_id: str, entry_id: str) -> TranslationMemoryRecord | None:
        project = self._project_repository.get(project_id)
        entry = project.get_entry(entry_id)
        return self._translation_memory.find_exact(
            project.source_language,
            project.target_language,
            entry.source,
            entry.context or "",
        )

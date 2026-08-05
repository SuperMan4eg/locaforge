"""Ranked translation memory suggestion workflow."""

from __future__ import annotations

from collections import Counter

from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.services.placeholder_protector import PlaceholderProtector
from locaforge.application.services.translation_validator import TranslationValidator
from locaforge.domain.translation_memory import TranslationMemoryMatch


class FindTranslationMemoryMatches:
    def __init__(
        self,
        project_repository: ProjectRepository,
        translation_memory: TranslationMemoryStore,
        translation_validator: TranslationValidator | None = None,
        placeholder_protector: PlaceholderProtector | None = None,
    ) -> None:
        self._project_repository = project_repository
        self._translation_memory = translation_memory
        self._translation_validator = translation_validator or TranslationValidator()
        self._placeholder_protector = placeholder_protector or PlaceholderProtector()

    def execute(
        self,
        project_id: str,
        entry_id: str,
        limit: int = 5,
        minimum_score: float = 0.6,
    ) -> tuple[TranslationMemoryMatch, ...]:
        project = self._project_repository.get(project_id)
        entry = project.get_entry(entry_id)
        matches = self._translation_memory.find_similar(
            project.source_language,
            project.target_language,
            entry.source,
            entry.context or "",
            limit=limit * 5,
            minimum_score=minimum_score,
        )
        source_placeholders = Counter(self._placeholder_protector.extract(entry.source))
        safe_matches = tuple(
            match
            for match in matches
            if not self._translation_validator.validate(entry, match.record.translation)
            and Counter(
                self._placeholder_protector.extract(match.record.translation)
            )
            == source_placeholders
        )
        return safe_matches[:limit]

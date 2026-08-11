"""Translation-memory and glossary operations for an open project."""

from __future__ import annotations

from pathlib import Path

from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.glossary_csv import GlossaryCsvFormat
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.use_cases.find_translation_memory_match import (
    FindTranslationMemoryMatch,
)
from locaforge.application.use_cases.find_translation_memory_matches import (
    FindTranslationMemoryMatches,
)
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.project import Project
from locaforge.domain.translation_memory import (
    TranslationMemoryMatch,
    TranslationMemoryRecord,
)


class TerminologyService:
    """Coordinate optional terminology stores without presentation concerns."""

    def __init__(
        self,
        translation_memory: TranslationMemoryStore | None,
        glossary: GlossaryStore | None,
        glossary_csv_format: GlossaryCsvFormat | None,
    ) -> None:
        self._translation_memory = translation_memory
        self._glossary = glossary
        self._glossary_csv_format = glossary_csv_format

    def translation_memory_match(
        self, repository: ProjectRepository, project: Project, entry_id: str
    ) -> TranslationMemoryRecord | None:
        if self._translation_memory is None:
            return None
        return FindTranslationMemoryMatch(repository, self._translation_memory).execute(
            project.id, entry_id
        )

    def translation_memory_matches(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_id: str,
        limit: int = 5,
        minimum_score: float = 0.6,
    ) -> tuple[TranslationMemoryMatch, ...]:
        if self._translation_memory is None:
            return ()
        return FindTranslationMemoryMatches(
            repository, self._translation_memory
        ).execute(project.id, entry_id, limit, minimum_score)

    def translation_memory_records(
        self, source_language: str = "", target_language: str = "", search: str = ""
    ) -> tuple[TranslationMemoryRecord, ...]:
        if self._translation_memory is None:
            return ()
        return self._translation_memory.list_records(
            source_language, target_language, search
        )

    def store_translation_memory_record(self, record: TranslationMemoryRecord) -> None:
        if self._translation_memory is None:
            raise RuntimeError("Translation memory is not configured")
        self._translation_memory.store(record)

    def delete_translation_memory_record(self, record: TranslationMemoryRecord) -> None:
        if self._translation_memory is None:
            raise RuntimeError("Translation memory is not configured")
        self._translation_memory.delete(record)

    def glossary_terms(self, project: Project) -> tuple[GlossaryTerm, ...]:
        if self._glossary is None:
            return ()
        return self._glossary.list_terms(
            project.source_language, project.target_language
        )

    def store_glossary_term(
        self,
        project: Project,
        source: str,
        target: str,
        case_sensitive: bool = False,
    ) -> GlossaryTerm:
        if self._glossary is None:
            raise RuntimeError("No glossary is configured")
        term = GlossaryTerm(
            project.source_language,
            project.target_language,
            source,
            target,
            case_sensitive,
        )
        self._glossary.store(term)
        return term

    def remove_glossary_term(self, project: Project, term: GlossaryTerm) -> None:
        if self._glossary is None:
            raise RuntimeError("No glossary is configured")
        if (
            term.source_language != project.source_language
            or term.target_language != project.target_language
        ):
            raise ValueError("Glossary term belongs to another language pair")
        self._glossary.remove(term)

    def import_glossary_csv(self, project: Project, path: Path) -> int:
        if self._glossary is None or self._glossary_csv_format is None:
            raise RuntimeError("Glossary CSV support is not configured")
        terms = self._glossary_csv_format.import_file(
            path, project.source_language, project.target_language
        )
        for term in terms:
            self._glossary.store(term)
        return len(terms)

    def export_glossary_csv(self, project: Project, path: Path) -> None:
        if self._glossary_csv_format is None:
            raise RuntimeError("Glossary CSV support is not configured")
        self._glossary_csv_format.export_file(self.glossary_terms(project), path)

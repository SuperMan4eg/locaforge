"""Apply one translation to matching source strings in a project."""

from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.use_cases.edit_translation import EditTranslation


class ApplyTranslationToMatches:
    def __init__(
        self,
        project_repository: ProjectRepository,
        translation_memory: TranslationMemoryStore | None = None,
        glossary: GlossaryStore | None = None,
    ) -> None:
        self._project_repository = project_repository
        self._translation_memory = translation_memory
        self._glossary = glossary

    def matching_entry_ids(self, project_id: str, entry_id: str) -> tuple[str, ...]:
        project = self._project_repository.get(project_id)
        selected = project.get_entry(entry_id)
        return tuple(
            entry.id
            for entry in project.entries
            if not entry.locked
            and entry.source == selected.source
            and entry.context == selected.context
        )

    def execute(
        self, project_id: str, entry_id: str, translation: str
    ) -> tuple[str, ...]:
        entry_ids = self.matching_entry_ids(project_id, entry_id)
        editor = EditTranslation(
            self._project_repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        )
        for matching_entry_id in entry_ids:
            editor.execute(project_id, matching_entry_id, translation)
        return entry_ids

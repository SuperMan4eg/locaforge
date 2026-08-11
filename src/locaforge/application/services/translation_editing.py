"""Undoable manual and bulk translation editing operations."""

from __future__ import annotations

from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.services.project_history import ProjectHistoryService
from locaforge.application.use_cases.apply_translation_to_matches import (
    ApplyTranslationToMatches,
)
from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.replace_translations import ReplaceTranslations
from locaforge.application.use_cases.validate_project import ValidateProject
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project


class TranslationEditingService:
    """Apply edits through domain use cases and record their history snapshots."""

    def __init__(
        self,
        translation_memory: TranslationMemoryStore | None,
        glossary: GlossaryStore | None,
    ) -> None:
        self._translation_memory = translation_memory
        self._glossary = glossary

    def edit(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_id: str,
        translation: str | None,
    ) -> TranslationEntry:
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, (entry_id,)
        )
        entry = EditTranslation(repository, glossary=self._glossary).execute(
            project.id, entry_id, translation
        )
        repository.record_translation_operation(
            project.id, previous_entries, previous_issues, "Edit translation"
        )
        return entry

    def select_candidate(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_id: str,
        candidate: str,
    ) -> TranslationEntry:
        entry = project.get_entry(entry_id)
        translation = (
            entry.model_translation
            if candidate == "model"
            else entry.reviewer_translation
            if candidate == "reviewer"
            else None
        )
        if candidate not in {"model", "reviewer"}:
            raise ValueError(f"Unknown translation candidate: {candidate!r}")
        if translation is None:
            raise ValueError(f"No {candidate} translation is available")
        return self.edit(repository, project, entry_id, translation)

    def replace(
        self,
        repository: ProjectRepository,
        project: Project,
        search_text: str,
        replacement_text: str,
    ) -> tuple[str, ...]:
        candidate_ids = tuple(
            entry.id
            for entry in project.entries
            if not entry.locked
            and entry.translation is not None
            and search_text in entry.translation
        )
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, candidate_ids
        )
        updated_entry_ids = ReplaceTranslations(
            repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        ).execute(project.id, search_text, replacement_text)
        history.record_updated_entries(
            repository,
            project.id,
            updated_entry_ids,
            previous_entries,
            previous_issues,
            "Replace translations",
        )
        return updated_entry_ids

    @staticmethod
    def matching_entry_ids(
        repository: ProjectRepository, project: Project, entry_id: str
    ) -> tuple[str, ...]:
        return ApplyTranslationToMatches(repository).matching_entry_ids(
            project.id, entry_id
        )

    def apply_to_matches(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_id: str,
        translation: str,
    ) -> tuple[str, ...]:
        operation = ApplyTranslationToMatches(
            repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        )
        matching_entry_ids = operation.matching_entry_ids(project.id, entry_id)
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, matching_entry_ids
        )
        updated_entry_ids = operation.execute(project.id, entry_id, translation)
        ValidateProject(repository, glossary=self._glossary).execute(project.id)
        history.record_updated_entries(
            repository,
            project.id,
            updated_entry_ids,
            previous_entries,
            previous_issues,
            "Apply translation to matches",
        )
        return updated_entry_ids

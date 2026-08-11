"""Project validation and workflow entry selections."""

from __future__ import annotations

from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ProjectValidationResult,
)
from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.use_cases.validate_project import ValidateProject
from locaforge.domain.entry import EntryStatus
from locaforge.domain.project import Project


class ProjectValidationService:
    """Validate an aggregate and select entries eligible for workflow actions."""

    def __init__(self, glossary: GlossaryStore | None) -> None:
        self._glossary = glossary

    @staticmethod
    def issues(
        repository: ProjectRepository, project: Project
    ) -> tuple[EntryValidationIssue, ...]:
        return repository.list_validation_issues(project.id)

    def validate(
        self, repository: ProjectRepository, project: Project
    ) -> ProjectValidationResult:
        return ValidateProject(repository, glossary=self._glossary).execute(project.id)

    @staticmethod
    def untranslated_entry_ids(project: Project) -> tuple[str, ...]:
        return tuple(
            entry.id
            for entry in project.entries
            if entry.status is EntryStatus.UNTRANSLATED and not entry.locked
        )

    @staticmethod
    def reviewable_entry_ids(project: Project) -> tuple[str, ...]:
        return tuple(
            entry.id
            for entry in project.entries
            if entry.status is EntryStatus.NEEDS_REVIEW
            and entry.translation is not None
            and not entry.locked
        )

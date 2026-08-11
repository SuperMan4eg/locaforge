"""Persistent project history orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from locaforge.application.dto.validation import ValidationIssue
from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.use_cases.restore_entry_revision import RestoreEntryRevision
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.history import EntryRevision, ProjectOperation
from locaforge.domain.project import Project

type OperationSnapshot = tuple[
    tuple[TranslationEntry, ...],
    dict[str, tuple[ValidationIssue, ...]],
]


class ProjectHistoryService:
    """Coordinate persistent undo/redo operations through a repository port."""

    def snapshot(
        self,
        repository: ProjectRepository,
        project_id: str,
        entry_ids: Sequence[str],
    ) -> OperationSnapshot:
        selected_ids = tuple(dict.fromkeys(entry_ids))
        entries = repository.get_entries(project_id, selected_ids)
        selected = set(selected_ids)
        issues: dict[str, list[ValidationIssue]] = {
            entry_id: [] for entry_id in selected_ids
        }
        for issue in repository.list_validation_issues(project_id):
            if issue.entry_id in selected:
                issues[issue.entry_id].append(
                    ValidationIssue(issue.code, issue.message)
                )
        return entries, {
            entry_id: tuple(entry_issues)
            for entry_id, entry_issues in issues.items()
        }

    def record_updated_entries(
        self,
        repository: ProjectRepository,
        project_id: str,
        updated_entry_ids: Sequence[str],
        previous_entries: Sequence[TranslationEntry],
        previous_issues: Mapping[str, Sequence[ValidationIssue]],
        label: str,
    ) -> None:
        updated = set(updated_entry_ids)
        repository.record_translation_operation(
            project_id,
            tuple(entry for entry in previous_entries if entry.id in updated),
            previous_issues,
            label,
        )

    def entry_revisions(
        self,
        repository: ProjectRepository,
        project_id: str,
        entry_id: str,
        limit: int = 50,
    ) -> tuple[EntryRevision, ...]:
        return repository.list_entry_revisions(project_id, entry_id, limit)

    def operations(
        self,
        repository: ProjectRepository,
        project_id: str,
        limit: int = 50,
    ) -> tuple[ProjectOperation, ...]:
        return repository.list_translation_operations(project_id, limit)

    def restore_revision(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_id: str,
        revision_id: int,
        translation_memory: TranslationMemoryStore | None = None,
        glossary: GlossaryStore | None = None,
    ) -> TranslationEntry:
        previous_entries, previous_issues = self.snapshot(
            repository, project.id, (entry_id,)
        )
        entry = RestoreEntryRevision(
            repository,
            translation_memory=translation_memory,
            glossary=glossary,
        ).execute(project.id, entry_id, revision_id)
        repository.record_translation_operation(
            project.id,
            previous_entries,
            previous_issues,
            "Restore translation revision",
        )
        return entry

    def can_undo(self, repository: ProjectRepository, project_id: str) -> bool:
        return repository.has_undoable_translation_operation(project_id)

    def next_undo_label(
        self, repository: ProjectRepository, project_id: str
    ) -> str | None:
        return repository.next_undo_operation_label(project_id)

    def undo(
        self, repository: ProjectRepository, project_id: str
    ) -> tuple[TranslationEntry, ...]:
        restored = repository.undo_last_translation_operation(project_id)
        if not restored:
            raise ValueError("There is no translation operation to undo")
        return restored

    def can_redo(self, repository: ProjectRepository, project_id: str) -> bool:
        return repository.has_redoable_translation_operation(project_id)

    def next_redo_label(
        self, repository: ProjectRepository, project_id: str
    ) -> str | None:
        return repository.next_redo_operation_label(project_id)

    def redo(
        self, repository: ProjectRepository, project_id: str
    ) -> tuple[TranslationEntry, ...]:
        restored = repository.redo_last_translation_operation(project_id)
        if not restored:
            raise ValueError("There is no translation operation to redo")
        return restored

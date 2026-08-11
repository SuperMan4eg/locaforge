"""Undoable approval and lock state operations for translation entries."""

from __future__ import annotations

from collections.abc import Sequence

from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.services.project_history import ProjectHistoryService
from locaforge.application.use_cases.set_entries_approval import SetEntriesApproval
from locaforge.application.use_cases.set_entries_locked import SetEntriesLocked
from locaforge.application.use_cases.set_entry_approval import SetEntryApproval
from locaforge.application.use_cases.set_entry_locked import SetEntryLocked
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project
from locaforge.domain.translation_memory import TranslationMemoryRecord


class EntryStateService:
    """Change review and lock state while preserving history and approved memory."""

    def __init__(self, translation_memory: TranslationMemoryStore | None) -> None:
        self._translation_memory = translation_memory

    def set_approval(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_id: str,
        approved: bool,
    ) -> TranslationEntry:
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, (entry_id,)
        )
        entry = SetEntryApproval(repository).execute(project.id, entry_id, approved)
        repository.record_translation_operation(
            project.id,
            previous_entries,
            previous_issues,
            "Approve translation" if approved else "Reopen translation",
        )
        if approved:
            self._store_approved(project, entry)
        return entry

    def set_locked(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_id: str,
        locked: bool,
    ) -> TranslationEntry:
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, (entry_id,)
        )
        entry = SetEntryLocked(repository).execute(project.id, entry_id, locked)
        repository.record_translation_operation(
            project.id,
            previous_entries,
            previous_issues,
            "Lock translation" if locked else "Unlock translation",
        )
        return entry

    def set_approvals(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_ids: Sequence[str],
        approved: bool,
    ) -> tuple[str, ...]:
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, entry_ids
        )
        updated_entry_ids = SetEntriesApproval(repository).execute(
            project.id, entry_ids, approved
        )
        history.record_updated_entries(
            repository,
            project.id,
            updated_entry_ids,
            previous_entries,
            previous_issues,
            "Approve translations" if approved else "Reopen translations",
        )
        if approved:
            for entry_id in updated_entry_ids:
                self._store_approved(project, repository.get_entry(project.id, entry_id))
        return updated_entry_ids

    def set_locks(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_ids: Sequence[str],
        locked: bool,
    ) -> tuple[str, ...]:
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, entry_ids
        )
        updated_entry_ids = SetEntriesLocked(repository).execute(
            project.id, entry_ids, locked
        )
        history.record_updated_entries(
            repository,
            project.id,
            updated_entry_ids,
            previous_entries,
            previous_issues,
            "Lock translations" if locked else "Unlock translations",
        )
        return updated_entry_ids

    def _store_approved(self, project: Project, entry: TranslationEntry) -> None:
        if self._translation_memory is None or entry.translation is None:
            return
        self._translation_memory.store(
            TranslationMemoryRecord(
                project.source_language,
                project.target_language,
                entry.source,
                entry.translation,
                entry.context or "",
            )
        )

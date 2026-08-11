"""Persistence port for projects and their entries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from locaforge.application.dto.validation import EntryValidationIssue, ValidationIssue
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.history import EntryRevision, ProjectOperation
from locaforge.domain.project import Project


class ProjectRepository(Protocol):
    def create(self, project: Project) -> None: ...

    def get(self, project_id: str) -> Project: ...

    def save(self, project: Project) -> None: ...

    def mark_project_saved(self, project_id: str) -> None: ...

    def mark_project_dirty(self, project_id: str) -> None: ...

    def is_project_dirty(self, project_id: str) -> bool: ...

    def get_entry(self, project_id: str, entry_id: str) -> TranslationEntry: ...

    def get_entries(
        self, project_id: str, entry_ids: Sequence[str]
    ) -> tuple[TranslationEntry, ...]: ...

    def update_entry(self, project_id: str, entry: TranslationEntry) -> None: ...

    def update_entries(
        self, project_id: str, entries: Sequence[TranslationEntry]
    ) -> None: ...

    def update_entry_statuses(
        self, project_id: str, entries: Sequence[TranslationEntry]
    ) -> None: ...

    def remove_documents(self, project_id: str, document_ids: Sequence[str]) -> None: ...

    def remove_entry_artifacts(
        self,
        project_id: str,
        removed_entry_ids: Sequence[str],
        reset_validation_entry_ids: Sequence[str] = (),
    ) -> None: ...

    def list_entry_revisions(
        self, project_id: str, entry_id: str, limit: int = 50
    ) -> tuple[EntryRevision, ...]: ...

    def get_entry_revision(
        self, project_id: str, entry_id: str, revision_id: int
    ) -> EntryRevision: ...

    def replace_validation_issues(
        self, project_id: str, entry_id: str, issues: Sequence[ValidationIssue]
    ) -> None: ...

    def replace_validation_issues_bulk(
        self,
        project_id: str,
        issues_by_entry: Mapping[str, Sequence[ValidationIssue]],
    ) -> None: ...

    def list_validation_issues(self, project_id: str) -> tuple[EntryValidationIssue, ...]: ...

    def record_translation_operation(
        self,
        project_id: str,
        previous_entries: Sequence[TranslationEntry],
        previous_issues: Mapping[str, Sequence[ValidationIssue]],
        label: str,
    ) -> None: ...

    def next_undo_operation_label(self, project_id: str) -> str | None: ...

    def next_redo_operation_label(self, project_id: str) -> str | None: ...

    def list_translation_operations(
        self, project_id: str, limit: int = 50
    ) -> tuple[ProjectOperation, ...]: ...

    def has_undoable_translation_operation(self, project_id: str) -> bool: ...

    def undo_last_translation_operation(
        self, project_id: str
    ) -> tuple[TranslationEntry, ...]: ...

    def has_redoable_translation_operation(self, project_id: str) -> bool: ...

    def redo_last_translation_operation(
        self, project_id: str
    ) -> tuple[TranslationEntry, ...]: ...

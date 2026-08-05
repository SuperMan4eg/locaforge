"""Batch translation review approval workflow."""

from __future__ import annotations

from collections.abc import Sequence

from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.domain.entry import EntryStatus


class SetEntriesApproval:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self._project_repository = project_repository

    def execute(
        self,
        project_id: str,
        entry_ids: Sequence[str],
        approved: bool,
    ) -> tuple[str, ...]:
        project = self._project_repository.get(project_id)
        entries = [project.get_entry(entry_id) for entry_id in dict.fromkeys(entry_ids)]
        if approved:
            entries_with_issues = {
                issue.entry_id
                for issue in self._project_repository.list_validation_issues(project_id)
            }
            invalid_entries = [
                entry.id
                for entry in entries
                if entry.translation is None or entry.id in entries_with_issues
            ]
            if invalid_entries:
                raise ValueError(
                    "Selected translations cannot be approved until validation issues are fixed"
                )
            changed_entries = [
                entry for entry in entries if entry.status is not EntryStatus.APPROVED
            ]
            for entry in changed_entries:
                entry.approve()
        else:
            changed_entries = [
                entry for entry in entries if entry.status is EntryStatus.APPROVED
            ]
            for entry in changed_entries:
                entry.reopen_review()
        for entry in changed_entries:
            self._project_repository.update_entry(project_id, entry)
        return tuple(entry.id for entry in changed_entries)

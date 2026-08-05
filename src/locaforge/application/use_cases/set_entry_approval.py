"""Translation review approval workflow."""

from __future__ import annotations

from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.domain.entry import EntryStatus, TranslationEntry


class SetEntryApproval:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self._project_repository = project_repository

    def execute(
        self,
        project_id: str,
        entry_id: str,
        approved: bool,
    ) -> TranslationEntry:
        project = self._project_repository.get(project_id)
        entry = project.get_entry(entry_id)
        if approved and entry.status is EntryStatus.APPROVED:
            return entry
        if not approved and entry.status is not EntryStatus.APPROVED:
            return entry
        if approved:
            has_issues = any(
                issue.entry_id == entry_id
                for issue in self._project_repository.list_validation_issues(project_id)
            )
            if has_issues:
                raise ValueError("A translation with validation issues cannot be approved")
            entry.approve()
        else:
            entry.reopen_review()
        self._project_repository.update_entry(project_id, entry)
        return entry

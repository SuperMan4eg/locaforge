"""Translation entry locking workflow."""

from __future__ import annotations

from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.domain.entry import TranslationEntry


class SetEntryLocked:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self._project_repository = project_repository

    def execute(
        self,
        project_id: str,
        entry_id: str,
        locked: bool,
    ) -> TranslationEntry:
        project = self._project_repository.get(project_id)
        entry = project.get_entry(entry_id)
        if entry.locked == locked:
            return entry
        entry.set_locked(locked)
        self._project_repository.update_entry(project_id, entry)
        return entry

"""Batch translation entry locking workflow."""

from __future__ import annotations

from collections.abc import Sequence

from locaforge.application.ports.project_repository import ProjectRepository


class SetEntriesLocked:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self._project_repository = project_repository

    def execute(
        self,
        project_id: str,
        entry_ids: Sequence[str],
        locked: bool,
    ) -> tuple[str, ...]:
        project = self._project_repository.get(project_id)
        entries = [project.get_entry(entry_id) for entry_id in dict.fromkeys(entry_ids)]
        if locked and any(entry.translation is None for entry in entries):
            raise ValueError("Selected untranslated entries cannot be locked")
        changed_entries = [entry for entry in entries if entry.locked != locked]
        for entry in changed_entries:
            entry.set_locked(locked)
        for entry in changed_entries:
            self._project_repository.update_entry(project_id, entry)
        return tuple(entry.id for entry in changed_entries)

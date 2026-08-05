"""Project save workflow."""

from __future__ import annotations

from locaforge.application.ports.project_repository import ProjectRepository


class SaveProject:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self._project_repository = project_repository

    def execute(self, project_id: str) -> None:
        project = self._project_repository.get(project_id)
        was_dirty = project.dirty
        project.mark_saved()
        try:
            self._project_repository.save(project)
        except Exception:
            if was_dirty:
                project.dirty = True
            raise

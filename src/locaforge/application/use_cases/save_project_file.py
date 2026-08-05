"""Persist an open project's database and portable container."""

from pathlib import Path

from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.project_session import ProjectSession
from locaforge.domain.project import Project


class SaveProjectFile:
    def __init__(
        self,
        project_container: ProjectContainer,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._project_container = project_container
        self._repository_factory = repository_factory

    def execute(self, session: ProjectSession, destination: Path | None = None) -> Project:
        target_path = destination or session.container_path
        if target_path is None:
            raise ValueError("A destination is required for a project that has not been saved")

        repository = self._repository_factory.create(session.database_path)
        project = repository.get(session.project_id)
        was_dirty = project.dirty
        project.mark_saved()
        repository.save(project)
        try:
            self._project_container.save(session, target_path)
        except Exception:
            if was_dirty:
                project.dirty = True
                repository.save(project)
            raise
        return project

"""Open, recover, save, and autosave portable projects."""

from __future__ import annotations

from pathlib import Path

from locaforge.application.dto.project import OpenedProject
from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.project_session import ProjectSession
from locaforge.application.use_cases.open_project_file import OpenProjectFile
from locaforge.application.use_cases.save_project_file import SaveProjectFile
from locaforge.domain.project import Project


class ProjectPersistenceService:
    """Coordinate the portable container with its project repository."""

    def __init__(
        self,
        project_container: ProjectContainer,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._project_container = project_container
        self._repository_factory = repository_factory

    @staticmethod
    def backup_path(path: Path) -> Path:
        return path.with_suffix(f"{path.suffix}.bak")

    def open(self, path: Path) -> OpenedProject:
        return OpenProjectFile(
            self._project_container, self._repository_factory
        ).execute(path)

    def open_backup(self, original_path: Path) -> OpenedProject:
        opened = self.open(self.backup_path(original_path))
        opened.session.container_path = None
        opened.session.metadata["recovered_from"] = str(original_path)
        repository = self._repository_factory.create(opened.session.database_path)
        repository.mark_project_dirty(opened.project.id)
        opened.project.dirty = True
        return opened

    def save(
        self, session: ProjectSession, destination: Path | None = None
    ) -> Project:
        return SaveProjectFile(
            self._project_container, self._repository_factory
        ).execute(session, destination)

    def autosave(
        self,
        repository: ProjectRepository,
        session: ProjectSession,
        project: Project,
    ) -> None:
        if session.container_path is None:
            raise ValueError(
                "A destination is required for a project that has not been saved"
            )
        repository.mark_project_saved(project.id)
        self._project_container.save_snapshot(session, session.container_path)

    @staticmethod
    def refresh_dirty_state(
        repository: ProjectRepository, project: Project
    ) -> None:
        project.dirty = repository.is_project_dirty(project.id)

"""Open a portable LocaForge project container."""

from pathlib import Path

from locaforge.application.dto.project import OpenedProject
from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory


class OpenProjectFile:
    def __init__(
        self,
        project_container: ProjectContainer,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._project_container = project_container
        self._repository_factory = repository_factory

    def execute(self, path: Path) -> OpenedProject:
        session = self._project_container.open(path)
        repository = self._repository_factory.create(session.database_path)
        project = repository.get(session.project_id)
        return OpenedProject(project=project, session=session)

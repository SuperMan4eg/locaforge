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
        if project.documents and project.documents[0].source_format == "legacy":
            source_file = session.metadata.get("source_file", project.name)
            source_format = session.metadata.get("source_format", "legacy")
            project.configure_single_document(
                Path(source_file if isinstance(source_file, str) else project.name),
                source_format if isinstance(source_format, str) else "legacy",
            )
        return OpenedProject(project=project, session=session)

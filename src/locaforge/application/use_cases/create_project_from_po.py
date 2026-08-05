"""Create a portable LocaForge project from a gettext PO file."""

from pathlib import Path

from locaforge.application.dto.project import CreatedProject
from locaforge.application.ports.po_format import PoImporter
from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory


class CreateProjectFromPo:
    def __init__(
        self,
        po_importer: PoImporter,
        project_container: ProjectContainer,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._po_importer = po_importer
        self._project_container = project_container
        self._repository_factory = repository_factory

    def execute(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
    ) -> CreatedProject:
        if destination.suffix.lower() != ".lfproj":
            raise ValueError("Project destination must use the .lfproj extension")

        project = self._po_importer.import_file(
            source_path, source_language, target_language
        )
        session = self._project_container.create(
            {
                "project_id": project.id,
                "project_name": project.name,
                "source_file": source_path.name,
                "source_format": "po",
                "source_language": source_language,
                "target_language": target_language,
            }
        )
        repository = self._repository_factory.create(session.database_path)
        repository.create(project)
        self._project_container.save(session, destination)
        return CreatedProject(project=project, session=session)

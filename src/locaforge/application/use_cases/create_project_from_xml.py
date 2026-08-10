"""Create a portable LocaForge project from an XML source file."""

from pathlib import Path

from locaforge.application.dto.project import CreatedProject
from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.ports.xml_format import XmlFieldMapping, XmlImporter


class CreateProjectFromXml:
    def __init__(
        self,
        xml_importer: XmlImporter,
        project_container: ProjectContainer,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._xml_importer = xml_importer
        self._project_container = project_container
        self._repository_factory = repository_factory

    def execute(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: XmlFieldMapping | None = None,
    ) -> CreatedProject:
        if destination.suffix.lower() != ".lfproj":
            raise ValueError("Project destination must use the .lfproj extension")
        project = self._xml_importer.import_file(
            source_path, source_language, target_language, field_mapping
        )
        project.configure_single_document(
            source_path,
            "xml",
            {
                "attribute_names": list(field_mapping.attribute_names)
                if field_mapping is not None
                else []
            },
        )
        session = self._project_container.create(
            {
                "project_id": project.id,
                "project_name": project.name,
                "source_file": source_path.name,
                "source_format": "xml",
                "source_language": source_language,
                "target_language": target_language,
            }
        )
        repository = self._repository_factory.create(session.database_path)
        repository.create(project)
        self._project_container.save(session, destination)
        return CreatedProject(project=project, session=session)

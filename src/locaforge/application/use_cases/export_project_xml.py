"""Export an open project back to XML."""

from pathlib import Path

from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.ports.xml_format import XmlExporter
from locaforge.application.project_session import ProjectSession


class ExportProjectXml:
    def __init__(
        self,
        xml_exporter: XmlExporter,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._xml_exporter = xml_exporter
        self._repository_factory = repository_factory

    def execute(self, session: ProjectSession, destination: Path) -> None:
        repository = self._repository_factory.create(session.database_path)
        project = repository.get(session.project_id)
        self._xml_exporter.export_file(project, destination)

"""Export an open project back to JSON."""

from pathlib import Path

from locaforge.application.ports.json_format import JsonExporter
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.project_session import ProjectSession


class ExportProjectJson:
    def __init__(
        self,
        json_exporter: JsonExporter,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._json_exporter = json_exporter
        self._repository_factory = repository_factory

    def execute(self, session: ProjectSession, destination: Path) -> None:
        repository = self._repository_factory.create(session.database_path)
        project = repository.get(session.project_id)
        self._json_exporter.export_file(project, destination)

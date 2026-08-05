"""Export an open project back to CSV or TSV."""

from pathlib import Path

from locaforge.application.ports.csv_format import CsvExporter
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.project_session import ProjectSession


class ExportProjectCsv:
    def __init__(
        self,
        csv_exporter: CsvExporter,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._csv_exporter = csv_exporter
        self._repository_factory = repository_factory

    def execute(self, session: ProjectSession, destination: Path) -> None:
        repository = self._repository_factory.create(session.database_path)
        project = repository.get(session.project_id)
        self._csv_exporter.export_file(project, destination)

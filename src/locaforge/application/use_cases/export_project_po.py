"""Export an open project back to gettext PO."""

from pathlib import Path

from locaforge.application.ports.po_format import PoExporter
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.project_session import ProjectSession


class ExportProjectPo:
    def __init__(
        self,
        po_exporter: PoExporter,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._po_exporter = po_exporter
        self._repository_factory = repository_factory

    def execute(self, session: ProjectSession, destination: Path) -> None:
        repository = self._repository_factory.create(session.database_path)
        project = repository.get(session.project_id)
        self._po_exporter.export_file(project, destination)

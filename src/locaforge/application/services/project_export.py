"""Project-level and multi-document localization export."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from locaforge.application.ports.csv_format import CsvExporter
from locaforge.application.ports.json_format import JsonExporter
from locaforge.application.ports.po_format import PoExporter
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.ports.xml_format import XmlExporter
from locaforge.application.project_session import ProjectSession
from locaforge.application.services.document_export import DocumentExportService
from locaforge.application.use_cases.export_project_csv import ExportProjectCsv
from locaforge.application.use_cases.export_project_json import ExportProjectJson
from locaforge.application.use_cases.export_project_po import ExportProjectPo
from locaforge.application.use_cases.export_project_xml import ExportProjectXml
from locaforge.domain.project import Project


class ProjectExportService:
    """Export an open project through configured format adapters."""

    def __init__(
        self,
        json_exporter: JsonExporter,
        repository_factory: ProjectRepositoryFactory,
        po_exporter: PoExporter | None = None,
        csv_exporter: CsvExporter | None = None,
        xml_exporter: XmlExporter | None = None,
    ) -> None:
        self._json_exporter = json_exporter
        self._repository_factory = repository_factory
        self._po_exporter = po_exporter
        self._csv_exporter = csv_exporter
        self._xml_exporter = xml_exporter

    def export_json(self, session: ProjectSession, destination: Path) -> None:
        ExportProjectJson(self._json_exporter, self._repository_factory).execute(
            session, destination
        )

    def export_po(self, session: ProjectSession, destination: Path) -> None:
        if self._po_exporter is None:
            raise RuntimeError("PO export support is not configured")
        ExportProjectPo(self._po_exporter, self._repository_factory).execute(
            session, destination
        )

    def export_csv(self, session: ProjectSession, destination: Path) -> None:
        if self._csv_exporter is None:
            raise RuntimeError("CSV export support is not configured")
        ExportProjectCsv(self._csv_exporter, self._repository_factory).execute(
            session, destination
        )

    def export_xml(self, session: ProjectSession, destination: Path) -> None:
        if self._xml_exporter is None:
            raise RuntimeError("XML export support is not configured")
        ExportProjectXml(self._xml_exporter, self._repository_factory).execute(
            session, destination
        )

    def export_documents(
        self,
        project: Project,
        document_ids: Sequence[str] | set[str] | frozenset[str],
        destination_directory: Path,
    ) -> tuple[Path, ...]:
        return DocumentExportService().export(
            project, document_ids, destination_directory, self._export_document
        )

    def export_all_documents(
        self, project: Project, destination_directory: Path
    ) -> tuple[Path, ...]:
        return self.export_documents(
            project,
            tuple(document.id for document in project.documents),
            destination_directory,
        )

    def _export_document(
        self, project: Project, source_format: str, destination: Path
    ) -> None:
        if source_format == "json":
            self._json_exporter.export_file(project, destination)
            return
        if source_format == "po" and self._po_exporter is not None:
            self._po_exporter.export_file(project, destination)
            return
        if source_format == "csv" and self._csv_exporter is not None:
            self._csv_exporter.export_file(project, destination)
            return
        if source_format == "xml" and self._xml_exporter is not None:
            self._xml_exporter.export_file(project, destination)
            return
        raise ValueError(f"Unsupported project document format: {source_format!r}")

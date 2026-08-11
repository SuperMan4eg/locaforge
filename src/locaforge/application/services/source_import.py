"""Import localization source files into new or existing projects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from locaforge.application.dto.project import CreatedProject
from locaforge.application.ports.csv_format import CsvFieldMapping, CsvImporter
from locaforge.application.ports.json_format import JsonFieldMapping, JsonImporter
from locaforge.application.ports.po_format import PoImporter
from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.ports.xml_format import XmlFieldMapping, XmlImporter
from locaforge.application.project_session import ProjectSession
from locaforge.application.services.document_refresh import ImportFieldMapping
from locaforge.application.services.document_workspace import DocumentWorkspaceService
from locaforge.application.services.project_path import is_safe_project_path
from locaforge.application.use_cases.create_project_from_csv import CreateProjectFromCsv
from locaforge.application.use_cases.create_project_from_json import CreateProjectFromJson
from locaforge.application.use_cases.create_project_from_po import CreateProjectFromPo
from locaforge.application.use_cases.create_project_from_xml import CreateProjectFromXml
from locaforge.domain.document import ProjectDocument
from locaforge.domain.project import Project


class SourceImportService:
    """Dispatch formats and coordinate multi-document project imports."""

    def __init__(
        self,
        json_importer: JsonImporter,
        project_container: ProjectContainer,
        repository_factory: ProjectRepositoryFactory,
        csv_importer: CsvImporter | None = None,
        po_importer: PoImporter | None = None,
        xml_importer: XmlImporter | None = None,
    ) -> None:
        self._json_importer = json_importer
        self._project_container = project_container
        self._repository_factory = repository_factory
        self._csv_importer = csv_importer
        self._po_importer = po_importer
        self._xml_importer = xml_importer

    def inspect_json_fields(self, path: Path) -> tuple[str, ...]:
        return self._json_importer.inspect_fields(path)

    def inspect_csv_fields(self, path: Path) -> tuple[str, ...]:
        if self._csv_importer is None:
            raise RuntimeError("CSV import support is not configured")
        return self._csv_importer.inspect_fields(path)

    def inspect_xml_attribute_names(self, path: Path) -> tuple[str, ...]:
        if self._xml_importer is None:
            raise RuntimeError("XML import support is not configured")
        return self._xml_importer.inspect_attribute_names(path)

    def create_from_json(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: JsonFieldMapping | None = None,
    ) -> CreatedProject:
        return CreateProjectFromJson(
            self._json_importer,
            self._project_container,
            self._repository_factory,
        ).execute(
            source_path, destination, source_language, target_language, field_mapping
        )

    def create_from_csv(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: CsvFieldMapping,
    ) -> CreatedProject:
        if self._csv_importer is None:
            raise RuntimeError("CSV import support is not configured")
        return CreateProjectFromCsv(
            self._csv_importer,
            self._project_container,
            self._repository_factory,
        ).execute(
            source_path,
            destination,
            source_language,
            target_language,
            field_mapping,
        )

    def create_from_po(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
    ) -> CreatedProject:
        if self._po_importer is None:
            raise RuntimeError("PO import support is not configured")
        return CreateProjectFromPo(
            self._po_importer,
            self._project_container,
            self._repository_factory,
        ).execute(source_path, destination, source_language, target_language)

    def create_from_xml(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: XmlFieldMapping | None = None,
    ) -> CreatedProject:
        if self._xml_importer is None:
            raise RuntimeError("XML import support is not configured")
        return CreateProjectFromXml(
            self._xml_importer,
            self._project_container,
            self._repository_factory,
        ).execute(
            source_path,
            destination,
            source_language,
            target_language,
            field_mapping,
        )

    def add_files(
        self,
        repository: ProjectRepository,
        session: ProjectSession,
        project: Project,
        source_paths: Sequence[Path],
        field_mappings: Mapping[Path, ImportFieldMapping] | None = None,
        document_paths: Mapping[Path, str] | None = None,
    ) -> tuple[ProjectDocument, ...]:
        if not source_paths:
            raise ValueError("Select at least one source file")
        normalized_paths = tuple(Path(path) for path in source_paths)
        existing_paths = {
            document.source_path.casefold() for document in project.documents
        }
        requested_paths = {
            path: (document_paths or {}).get(path, path.name).replace("\\", "/")
            for path in normalized_paths
        }
        normalized_document_paths = [value.casefold() for value in requested_paths.values()]
        if (
            len(normalized_document_paths) != len(set(normalized_document_paths))
            or existing_paths.intersection(normalized_document_paths)
        ):
            raise ValueError(
                "Imported files must have unique names or relative paths within the project"
            )
        for value in requested_paths.values():
            if not is_safe_project_path(value):
                raise ValueError(f"Unsafe project document path: {value!r}")
        mappings = field_mappings or {}
        imported_projects = [
            self.import_file(
                path,
                project.source_language,
                project.target_language,
                mappings.get(path),
            )
            for path in normalized_paths
        ]
        for source_path, imported in zip(
            normalized_paths, imported_projects, strict=True
        ):
            imported.documents[0].source_path = requested_paths[source_path]
        added_documents = tuple(
            document
            for imported in imported_projects
            for document in imported.documents
        )
        for imported in imported_projects:
            project.documents.extend(imported.documents)
            project.entries.extend(imported.entries)
        project.source_document = project.documents[0].source_document
        project.dirty = True
        DocumentWorkspaceService.sync_source_metadata(project, session.metadata)
        repository.save(project)
        return added_documents

    def create_from_files(
        self,
        source_paths: Sequence[Path],
        destination: Path,
        source_language: str,
        target_language: str,
        field_mappings: Mapping[Path, ImportFieldMapping] | None = None,
    ) -> CreatedProject:
        if not source_paths:
            raise ValueError("Select at least one source file")
        if destination.suffix.lower() != ".lfproj":
            raise ValueError("Project destination must use the .lfproj extension")
        normalized_paths = tuple(Path(path) for path in source_paths)
        source_names = [path.name.casefold() for path in normalized_paths]
        if len(source_names) != len(set(source_names)):
            raise ValueError("Imported files must have unique names")
        mappings = field_mappings or {}
        imported_projects = [
            self.import_file(path, source_language, target_language, mappings.get(path))
            for path in normalized_paths
        ]
        project = imported_projects[0]
        for imported in imported_projects[1:]:
            project.documents.extend(imported.documents)
            project.entries.extend(imported.entries)
        project.name = destination.stem
        project.dirty = False
        session = self._project_container.create(
            {
                "project_id": project.id,
                "project_name": project.name,
                "source_files": [path.name for path in normalized_paths],
                "source_format": "multiple",
                "source_language": source_language,
                "target_language": target_language,
            }
        )
        repository = self._repository_factory.create(session.database_path)
        repository.create(project)
        self._project_container.save(session, destination)
        return CreatedProject(project, session)

    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
        field_mapping: ImportFieldMapping,
    ) -> Project:
        suffix = path.suffix.lower()
        if suffix == ".json":
            json_mapping = (
                field_mapping if isinstance(field_mapping, JsonFieldMapping) else None
            )
            project = self._json_importer.import_file(
                path, source_language, target_language, json_mapping
            )
            project.configure_single_document(
                path, "json", self._serialize_mapping(field_mapping)
            )
            return project
        if suffix in {".csv", ".tsv"}:
            if self._csv_importer is None or not isinstance(field_mapping, CsvFieldMapping):
                raise ValueError(f"CSV field mapping is required for {path.name!r}")
            project = self._csv_importer.import_file(
                path, source_language, target_language, field_mapping
            )
            project.configure_single_document(
                path, "csv", self._serialize_mapping(field_mapping)
            )
            return project
        if suffix == ".po":
            if self._po_importer is None:
                raise RuntimeError("PO import support is not configured")
            project = self._po_importer.import_file(path, source_language, target_language)
            project.configure_single_document(path, "po")
            return project
        if suffix == ".xml":
            if self._xml_importer is None:
                raise RuntimeError("XML import support is not configured")
            xml_mapping = (
                field_mapping if isinstance(field_mapping, XmlFieldMapping) else None
            )
            project = self._xml_importer.import_file(
                path, source_language, target_language, xml_mapping
            )
            project.configure_single_document(
                path, "xml", self._serialize_mapping(field_mapping)
            )
            return project
        raise ValueError(f"Unsupported localization file format: {path.suffix or path.name}")

    @staticmethod
    def _serialize_mapping(mapping: ImportFieldMapping) -> dict[str, object]:
        if isinstance(mapping, (JsonFieldMapping, CsvFieldMapping)):
            return {
                "source_field": mapping.source_field,
                "target_field": mapping.target_field,
                "key_field": mapping.key_field,
                "import_existing_translations": mapping.import_existing_translations,
            }
        if isinstance(mapping, XmlFieldMapping):
            return {"attribute_names": list(mapping.attribute_names)}
        return {}

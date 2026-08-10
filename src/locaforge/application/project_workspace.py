"""Stateful application facade used by desktop presentation."""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from locaforge.application.dto.project import (
    DocumentRefreshPreview,
    ExportPreflight,
    ProjectStatistics,
)
from locaforge.application.dto.project_description import ProjectDescriptionRequest
from locaforge.application.dto.review import ReviewBatchResult
from locaforge.application.dto.translation import BatchResult
from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ProjectValidationResult,
    ValidationCode,
    ValidationIssue,
)
from locaforge.application.errors import ModelUnavailableError, NoOpenProjectError
from locaforge.application.ports.csv_format import (
    CsvExporter,
    CsvFieldMapping,
    CsvImporter,
)
from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.glossary_csv import GlossaryCsvFormat
from locaforge.application.ports.json_format import (
    JsonExporter,
    JsonFieldMapping,
    JsonImporter,
)
from locaforge.application.ports.llm import LLMClient
from locaforge.application.ports.po_format import PoExporter, PoImporter
from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_metadata_lookup import ProjectMetadataLookup
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.ports.xml_format import (
    XmlExporter,
    XmlFieldMapping,
    XmlImporter,
)
from locaforge.application.project_session import ProjectSession
from locaforge.application.use_cases.apply_translation_to_matches import (
    ApplyTranslationToMatches,
)
from locaforge.application.use_cases.create_project_from_csv import CreateProjectFromCsv
from locaforge.application.use_cases.create_project_from_json import CreateProjectFromJson
from locaforge.application.use_cases.create_project_from_po import CreateProjectFromPo
from locaforge.application.use_cases.create_project_from_xml import CreateProjectFromXml
from locaforge.application.use_cases.dismiss_ai_review_issue import DismissAiReviewIssue
from locaforge.application.use_cases.dismiss_ai_review_issues import DismissAiReviewIssues
from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.export_project_csv import ExportProjectCsv
from locaforge.application.use_cases.export_project_json import ExportProjectJson
from locaforge.application.use_cases.export_project_po import ExportProjectPo
from locaforge.application.use_cases.export_project_xml import ExportProjectXml
from locaforge.application.use_cases.find_translation_memory_match import (
    FindTranslationMemoryMatch,
)
from locaforge.application.use_cases.find_translation_memory_matches import (
    FindTranslationMemoryMatches,
)
from locaforge.application.use_cases.open_project_file import OpenProjectFile
from locaforge.application.use_cases.replace_translations import ReplaceTranslations
from locaforge.application.use_cases.restore_entry_revision import RestoreEntryRevision
from locaforge.application.use_cases.review_translations import ReviewTranslations
from locaforge.application.use_cases.save_project_file import SaveProjectFile
from locaforge.application.use_cases.set_entries_approval import SetEntriesApproval
from locaforge.application.use_cases.set_entries_locked import SetEntriesLocked
from locaforge.application.use_cases.set_entry_approval import SetEntryApproval
from locaforge.application.use_cases.set_entry_locked import SetEntryLocked
from locaforge.application.use_cases.translate_batch import TranslateBatch
from locaforge.application.use_cases.update_model_settings import UpdateModelSettings
from locaforge.application.use_cases.validate_project import ValidateProject
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.history import EntryRevision, ProjectOperation
from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile
from locaforge.domain.settings import ModelSettings
from locaforge.domain.translation_memory import (
    TranslationMemoryMatch,
    TranslationMemoryRecord,
)

type ProgressCallback = Callable[[int, int], None]
type CancellationCheck = Callable[[], bool]
type ImportFieldMapping = JsonFieldMapping | CsvFieldMapping | XmlFieldMapping | None


def _ignore_progress(completed: int, total: int) -> None:
    del completed, total


def _never_cancel() -> bool:
    return False


class ProjectWorkspace:
    """Owns the currently open project and exposes GUI-sized operations."""

    def __init__(
        self,
        json_importer: JsonImporter,
        json_exporter: JsonExporter,
        project_container: ProjectContainer,
        repository_factory: ProjectRepositoryFactory,
        llm_client: LLMClient | None = None,
        translation_memory: TranslationMemoryStore | None = None,
        glossary: GlossaryStore | None = None,
        glossary_csv_format: GlossaryCsvFormat | None = None,
        po_importer: PoImporter | None = None,
        po_exporter: PoExporter | None = None,
        csv_importer: CsvImporter | None = None,
        csv_exporter: CsvExporter | None = None,
        xml_importer: XmlImporter | None = None,
        xml_exporter: XmlExporter | None = None,
        project_metadata_lookup: ProjectMetadataLookup | None = None,
    ) -> None:
        self._json_importer = json_importer
        self._json_exporter = json_exporter
        self._project_container = project_container
        self._repository_factory = repository_factory
        self._llm_client = llm_client
        self._translation_memory = translation_memory
        self._glossary = glossary
        self._glossary_csv_format = glossary_csv_format
        self._po_importer = po_importer
        self._po_exporter = po_exporter
        self._csv_importer = csv_importer
        self._csv_exporter = csv_exporter
        self._xml_importer = xml_importer
        self._xml_exporter = xml_exporter
        self._project_metadata_lookup = project_metadata_lookup
        self._project: Project | None = None
        self._session: ProjectSession | None = None
        self._global_model_settings = ModelSettings()

    @property
    def has_project(self) -> bool:
        return self._project is not None and self._session is not None

    @property
    def project(self) -> Project:
        if self._project is None:
            raise NoOpenProjectError("No project is currently open")
        return self._project

    @property
    def session(self) -> ProjectSession:
        if self._session is None:
            raise NoOpenProjectError("No project is currently open")
        return self._session

    @property
    def global_model_settings(self) -> ModelSettings:
        return self._global_model_settings

    def set_global_model_settings(self, settings: ModelSettings) -> None:
        """Set application-wide settings used by projects without an override."""
        self._global_model_settings = settings

    def resolve_model_settings(self, project: Project | None = None) -> ModelSettings:
        """Return the effective model settings for a project or the application."""
        target = project if project is not None else self._project
        if target is not None and target.model_settings_override_enabled:
            return target.model_settings
        return self._global_model_settings

    @property
    def model_settings_source(self) -> str:
        return "project" if self.project.model_settings_override_enabled else "global"

    def create_from_json(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: JsonFieldMapping | None = None,
    ) -> Project:
        created = CreateProjectFromJson(
            self._json_importer,
            self._project_container,
            self._repository_factory,
        ).execute(
            source_path, destination, source_language, target_language, field_mapping
        )
        self._project = created.project
        self._session = created.session
        return self._project

    def generate_project_profile(
        self, name: str, *, use_online_lookup: bool = False
    ) -> ProjectProfile:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Enter a project name before generating its description")
        settings = self.resolve_model_settings()
        research_context = ""
        if use_online_lookup:
            if self._project_metadata_lookup is None:
                raise ModelUnavailableError("Online project lookup is not configured")
            research_context = self._project_metadata_lookup.lookup(normalized_name)
        return self._llm_client.describe_project(
            ProjectDescriptionRequest(
                normalized_name,
                settings.model,
                settings.timeout_seconds,
                research_context,
            )
        ).profile

    def create_project(
        self,
        destination: Path,
        name: str,
        source_language: str,
        target_language: str,
        profile: ProjectProfile | None = None,
    ) -> Project:
        """Create and open an empty project before any source files are imported."""
        if destination.suffix.lower() != ".lfproj":
            raise ValueError("Project destination must use the .lfproj extension")
        project = Project(
            id=str(uuid.uuid4()),
            name=name.strip(),
            source_language=source_language.strip(),
            target_language=target_language.strip(),
            profile=profile or ProjectProfile(),
        )
        session = self._project_container.create(
            {
                "project_id": project.id,
                "project_name": project.name,
                "source_files": [],
                "source_format": "multiple",
                "source_language": project.source_language,
                "target_language": project.target_language,
            }
        )
        repository = self._repository_factory.create(session.database_path)
        repository.create(project)
        self._project_container.save(session, destination)
        self._project = project
        self._session = session
        return project

    def import_files(
        self,
        source_paths: Sequence[Path],
        field_mappings: Mapping[Path, ImportFieldMapping] | None = None,
        document_paths: Mapping[Path, str] | None = None,
    ) -> tuple[ProjectDocument, ...]:
        """Import one or more source files into the currently open project."""
        if not source_paths:
            raise ValueError("Select at least one source file")
        normalized_paths = tuple(Path(path) for path in source_paths)
        existing_paths = {
            document.source_path.casefold() for document in self.project.documents
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
            relative_path = Path(value)
            if relative_path.is_absolute() or ".." in relative_path.parts or not value:
                raise ValueError(f"Unsafe project document path: {value!r}")
        mappings = field_mappings or {}
        imported_projects = [
            self._import_source_file(
                path,
                self.project.source_language,
                self.project.target_language,
                mappings.get(path),
            )
            for path in normalized_paths
        ]
        added_documents = tuple(
            document
            for imported in imported_projects
            for document in imported.documents
        )
        for imported in imported_projects:
            self.project.documents.extend(imported.documents)
            self.project.entries.extend(imported.entries)
        for source_path, imported in zip(
            normalized_paths, imported_projects, strict=True
        ):
            imported.documents[0].source_path = requested_paths[source_path]
        self.project.source_document = self.project.documents[0].source_document
        self.project.dirty = True
        self.session.metadata["source_files"] = [
            document.source_path for document in self.project.documents
        ]
        self.session.metadata["source_format"] = (
            self.project.documents[0].source_format
            if len(self.project.documents) == 1
            else "multiple"
        )
        self._repository().save(self.project)
        return added_documents

    def update_project_profile(
        self,
        name: str,
        source_language: str,
        target_language: str,
        profile: ProjectProfile,
    ) -> None:
        """Update project-owned metadata and persist it in the working database."""
        normalized_name = name.strip()
        normalized_source = source_language.strip()
        normalized_target = target_language.strip()
        if not normalized_name or not normalized_source or not normalized_target:
            raise ValueError("Project name and languages must not be empty")
        if normalized_source.casefold() == normalized_target.casefold():
            raise ValueError("Source and target languages must be different")
        project = self.project
        project.name = normalized_name
        project.source_language = normalized_source
        project.target_language = normalized_target
        project.profile = profile
        project.dirty = True
        self.session.metadata.update(
            {
                "project_name": normalized_name,
                "source_language": normalized_source,
                "target_language": normalized_target,
            }
        )
        self._repository().save(project)

    def remove_documents(self, document_ids: Sequence[str]) -> tuple[int, int]:
        """Remove documents and their project-owned data, never source files."""
        selected_ids = tuple(dict.fromkeys(document_ids))
        if not selected_ids:
            raise ValueError("Select at least one project file to remove")
        known_ids = {document.id for document in self.project.documents}
        if not set(selected_ids).issubset(known_ids):
            raise ValueError("One or more selected project files do not exist")
        entry_count = sum(
            entry.document_id in selected_ids for entry in self.project.entries
        )
        repository = self._repository()
        repository.remove_documents(self.project.id, selected_ids)
        self._reload(repository)
        self.project.source_document = (
            self.project.documents[0].source_document
            if self.project.documents
            else None
        )
        self.session.metadata["source_files"] = [
            document.source_path for document in self.project.documents
        ]
        self.session.metadata["source_format"] = (
            self.project.documents[0].source_format
            if len(self.project.documents) == 1
            else "multiple"
        )
        return len(selected_ids), entry_count

    def preview_document_refresh(
        self, document_ids: Sequence[str]
    ) -> DocumentRefreshPreview:
        _, _, preview, _, _ = self._prepare_document_refresh(document_ids)
        return preview

    def refresh_documents(
        self, document_ids: Sequence[str]
    ) -> DocumentRefreshPreview:
        refreshed_documents, refreshed_entries, preview, removed_ids, changed_ids = (
            self._prepare_document_refresh(document_ids)
        )
        selected_ids = {document.id for document in refreshed_documents}
        document_by_id = {document.id: document for document in refreshed_documents}
        self.project.documents = [
            document_by_id.get(document.id, document)
            for document in self.project.documents
        ]
        self.project.entries = [
            entry for entry in self.project.entries if entry.document_id not in selected_ids
        ]
        self.project.entries.extend(refreshed_entries)
        self.project.source_document = (
            self.project.documents[0].source_document if self.project.documents else None
        )
        self.project.dirty = True
        repository = self._repository()
        repository.remove_entry_artifacts(
            self.project.id, tuple(removed_ids), tuple(changed_ids)
        )
        repository.save(self.project)
        return preview

    def _prepare_document_refresh(
        self, document_ids: Sequence[str]
    ) -> tuple[
        list[ProjectDocument],
        list[TranslationEntry],
        DocumentRefreshPreview,
        set[str],
        set[str],
    ]:
        selected_ids = tuple(dict.fromkeys(document_ids))
        if not selected_ids:
            raise ValueError("Select at least one project file to refresh")
        documents = [
            document
            for document in self.project.documents
            if document.id in selected_ids
        ]
        if len(documents) != len(selected_ids):
            raise ValueError("One or more selected project files do not exist")
        refreshed_documents: list[ProjectDocument] = []
        refreshed_entries: list[TranslationEntry] = []
        new_count = changed_count = removed_count = unchanged_count = 0
        removed_ids: set[str] = set()
        changed_ids: set[str] = set()
        for document in documents:
            if not document.source_location:
                raise ValueError(f"Source location is not recorded for {document.source_path!r}")
            source_path = Path(document.source_location)
            if not source_path.is_file():
                raise ValueError(f"Source file no longer exists: {source_path}")
            mapping = self._restore_import_mapping(document)
            imported = self._import_source_file(
                source_path,
                self.project.source_language,
                self.project.target_language,
                mapping,
            )
            imported_document = imported.documents[0]
            imported_document.id = document.id
            imported_document.name = document.name
            imported_document.source_path = document.source_path
            imported_document.source_location = document.source_location
            imported_document.import_settings = dict(document.import_settings)
            old_entries = [
                entry for entry in self.project.entries if entry.document_id == document.id
            ]
            old_by_identity = {self._entry_refresh_identity(entry): entry for entry in old_entries}
            seen_identities: set[tuple[object, ...]] = set()
            for entry in imported.entries:
                identity = self._entry_refresh_identity(entry)
                if identity in seen_identities:
                    raise ValueError(f"Duplicate entry identity in {document.source_path!r}")
                seen_identities.add(identity)
                old_entry = old_by_identity.get(identity)
                entry.document_id = document.id
                if old_entry is None:
                    new_count += 1
                else:
                    entry.id = old_entry.id
                    entry.translation = old_entry.translation
                    if entry.source == old_entry.source:
                        entry.status = old_entry.status
                        entry.locked = old_entry.locked
                        entry.model_translation = old_entry.model_translation
                        entry.reviewer_translation = old_entry.reviewer_translation
                        unchanged_count += 1
                    else:
                        entry.status = (
                            EntryStatus.NEEDS_REVIEW
                            if old_entry.translation is not None
                            else EntryStatus.UNTRANSLATED
                        )
                        entry.locked = False
                        changed_ids.add(entry.id)
                        changed_count += 1
                refreshed_entries.append(entry)
            removed = set(old_by_identity) - seen_identities
            removed_entry_ids = {old_by_identity[identity].id for identity in removed}
            removed_ids.update(removed_entry_ids)
            removed_count += len(removed_entry_ids)
            refreshed_documents.append(imported_document)
        return (
            refreshed_documents,
            refreshed_entries,
            DocumentRefreshPreview(
                len(documents), new_count, changed_count, removed_count, unchanged_count
            ),
            removed_ids,
            changed_ids,
        )

    @staticmethod
    def _entry_refresh_identity(entry: TranslationEntry) -> tuple[object, ...]:
        return ("key", entry.key, entry.context) if entry.key and entry.key != entry.source else (
            "path",
            *entry.key_path,
        )

    @staticmethod
    def _restore_import_mapping(document: ProjectDocument) -> ImportFieldMapping:
        settings = document.import_settings
        if document.source_format == "json":
            if not settings:
                return None
            return JsonFieldMapping(
                str(settings["source_field"]),
                str(settings["target_field"]),
                str(settings["key_field"]) if settings.get("key_field") else None,
                bool(settings.get("import_existing_translations", True)),
            )
        if document.source_format == "csv":
            if not settings:
                raise ValueError(
                    f"CSV mapping is not recorded for {document.source_path!r}"
                )
            return CsvFieldMapping(
                str(settings["source_field"]),
                str(settings["target_field"]),
                str(settings["key_field"]) if settings.get("key_field") else None,
                bool(settings.get("import_existing_translations", True)),
            )
        if document.source_format == "xml":
            raw_names = settings.get("attribute_names", [])
            names = tuple(str(name) for name in raw_names) if isinstance(raw_names, list) else ()
            return XmlFieldMapping(names)
        if document.source_format == "po":
            return None
        raise ValueError(f"Unsupported project document format: {document.source_format!r}")

    def inspect_json_fields(self, path: Path) -> tuple[str, ...]:
        return self._json_importer.inspect_fields(path)

    def inspect_csv_fields(self, path: Path) -> tuple[str, ...]:
        if self._csv_importer is None:
            raise RuntimeError("CSV import support is not configured")
        return self._csv_importer.inspect_fields(path)

    def create_from_csv(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: CsvFieldMapping,
    ) -> Project:
        if self._csv_importer is None:
            raise RuntimeError("CSV import support is not configured")
        created = CreateProjectFromCsv(
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
        self._project = created.project
        self._session = created.session
        return self._project

    def create_from_po(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
    ) -> Project:
        if self._po_importer is None:
            raise RuntimeError("PO import support is not configured")
        created = CreateProjectFromPo(
            self._po_importer,
            self._project_container,
            self._repository_factory,
        ).execute(
            source_path, destination, source_language, target_language
        )
        self._project = created.project
        self._session = created.session
        return self._project

    def create_from_xml(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: XmlFieldMapping | None = None,
    ) -> Project:
        if self._xml_importer is None:
            raise RuntimeError("XML import support is not configured")
        created = CreateProjectFromXml(
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
        self._project = created.project
        self._session = created.session
        return self._project

    def create_from_files(
        self,
        source_paths: Sequence[Path],
        destination: Path,
        source_language: str,
        target_language: str,
        field_mappings: Mapping[Path, ImportFieldMapping] | None = None,
    ) -> Project:
        """Create one project from multiple localization files as a single transaction."""
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
            self._import_source_file(
                path,
                source_language,
                target_language,
                mappings.get(path),
            )
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
        self._project = project
        self._session = session
        return project

    def _import_source_file(
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
                path, "json", self._serialize_import_mapping(field_mapping)
            )
            return project
        if suffix in {".csv", ".tsv"}:
            if self._csv_importer is None or not isinstance(field_mapping, CsvFieldMapping):
                raise ValueError(f"CSV field mapping is required for {path.name!r}")
            project = self._csv_importer.import_file(
                path, source_language, target_language, field_mapping
            )
            project.configure_single_document(
                path, "csv", self._serialize_import_mapping(field_mapping)
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
                path, "xml", self._serialize_import_mapping(field_mapping)
            )
            return project
        raise ValueError(f"Unsupported localization file format: {path.suffix or path.name}")

    @staticmethod
    def _serialize_import_mapping(mapping: ImportFieldMapping) -> dict[str, object]:
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

    def inspect_xml_attribute_names(self, path: Path) -> tuple[str, ...]:
        if self._xml_importer is None:
            raise RuntimeError("XML import support is not configured")
        return self._xml_importer.inspect_attribute_names(path)

    def open(self, path: Path) -> Project:
        opened = OpenProjectFile(
            self._project_container, self._repository_factory
        ).execute(path)
        self._project = opened.project
        self._session = opened.session
        return self._project

    @staticmethod
    def backup_path(path: Path) -> Path:
        return path.with_suffix(f"{path.suffix}.bak")

    def open_backup(self, original_path: Path) -> Project:
        """Open the automatic backup as an unsaved recovery copy."""
        backup_path = self.backup_path(original_path)
        opened = OpenProjectFile(
            self._project_container, self._repository_factory
        ).execute(backup_path)
        opened.session.container_path = None
        opened.session.metadata["recovered_from"] = str(original_path)
        repository = self._repository_factory.create(opened.session.database_path)
        repository.mark_project_dirty(opened.project.id)
        opened.project.dirty = True
        self._project = opened.project
        self._session = opened.session
        return self._project

    def edit_translation(self, entry_id: str, translation: str | None) -> TranslationEntry:
        repository = self._repository()
        previous_entry = repository.get_entry(self.project.id, entry_id)
        previous_issues = {
            entry_id: tuple(
                ValidationIssue(issue.code, issue.message)
                for issue in repository.list_validation_issues(self.project.id)
                if issue.entry_id == entry_id
            )
        }
        entry = EditTranslation(repository, glossary=self._glossary).execute(
            self.project.id, entry_id, translation
        )
        repository.record_translation_operation(
            self.project.id, (previous_entry,), previous_issues, "Edit translation"
        )
        self._replace_entry(entry)
        return entry

    def select_translation_candidate(
        self, entry_id: str, candidate: str
    ) -> TranslationEntry:
        entry = self.project.get_entry(entry_id)
        translation = (
            entry.model_translation
            if candidate == "model"
            else entry.reviewer_translation
            if candidate == "reviewer"
            else None
        )
        if candidate not in {"model", "reviewer"}:
            raise ValueError(f"Unknown translation candidate: {candidate!r}")
        if translation is None:
            raise ValueError(f"No {candidate} translation is available")
        return self.edit_translation(entry_id, translation)

    def replace_translations(
        self, search_text: str, replacement_text: str
    ) -> tuple[str, ...]:
        repository = self._repository()
        candidate_ids = tuple(
            entry.id
            for entry in self.project.entries
            if not entry.locked
            and entry.translation is not None
            and search_text in entry.translation
        )
        previous_entries, previous_issues = self._operation_snapshot(
            repository, candidate_ids
        )
        updated_entry_ids = ReplaceTranslations(
            repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        ).execute(self.project.id, search_text, replacement_text)
        self._record_operation_for_updated_entries(
            repository,
            updated_entry_ids,
            previous_entries,
            previous_issues,
            "Replace translations",
        )
        self._reload(repository)
        return updated_entry_ids

    def matching_translation_entry_ids(self, entry_id: str) -> tuple[str, ...]:
        return ApplyTranslationToMatches(self._repository()).matching_entry_ids(
            self.project.id, entry_id
        )

    def apply_translation_to_matches(
        self, entry_id: str, translation: str
    ) -> tuple[str, ...]:
        repository = self._repository()
        apply_to_matches = ApplyTranslationToMatches(
            repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        )
        matching_entry_ids = apply_to_matches.matching_entry_ids(
            self.project.id, entry_id
        )
        previous_entries, previous_issues = self._operation_snapshot(
            repository, matching_entry_ids
        )
        updated_entry_ids = apply_to_matches.execute(
            self.project.id, entry_id, translation
        )
        ValidateProject(repository, glossary=self._glossary).execute(self.project.id)
        self._record_operation_for_updated_entries(
            repository,
            updated_entry_ids,
            previous_entries,
            previous_issues,
            "Apply translation to matches",
        )
        self._reload(repository)
        return updated_entry_ids

    def review_entries(
        self,
        entry_ids: Sequence[str],
        progress_callback: ProgressCallback | None = None,
        cancellation_check: CancellationCheck | None = None,
    ) -> ReviewBatchResult:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        repository = self._repository()
        reviewer = ReviewTranslations(repository, self._llm_client)
        reviewable_ids = {
            entry_id
            for entry_id in entry_ids
            if repository.get_entry(self.project.id, entry_id).translation is not None
        }
        previous_entries, previous_issues = self._operation_snapshot(
            repository, tuple(reviewable_ids)
        )
        settings = self.resolve_model_settings()
        report_progress = progress_callback or _ignore_progress
        is_cancelled = cancellation_check or _never_cancel
        reviewed_entries = 0
        changed_entry_ids: list[str] = []
        issue_count = 0
        cancelled = False
        report_progress(0, len(entry_ids))
        for offset in range(0, len(entry_ids), settings.batch_size):
            if is_cancelled():
                cancelled = True
                break
            batch_entry_ids = entry_ids[offset : offset + settings.batch_size]
            issue_count += reviewer.execute(
                self.project.id,
                batch_entry_ids,
                settings.effective_review_model,
                settings.timeout_seconds,
                settings.review_prompt,
                settings.review_reasoning,
            )
            changed_entry_ids.extend(
                entry_id for entry_id in batch_entry_ids if entry_id in reviewable_ids
            )
            reviewed_entries += len(batch_entry_ids)
            report_progress(reviewed_entries, len(entry_ids))
        self._record_operation_for_updated_entries(
            repository,
            changed_entry_ids,
            previous_entries,
            previous_issues,
            "Review translations",
        )
        if changed_entry_ids:
            self._reload(repository)
        return ReviewBatchResult(reviewed_entries, issue_count, cancelled)

    def dismiss_ai_review_issue(self, entry_id: str) -> None:
        repository = self._repository()
        previous_entries, previous_issues = self._operation_snapshot(
            repository, (entry_id,)
        )
        had_ai_issue = any(
            issue.code is ValidationCode.AI_REVIEW
            for issue in previous_issues[entry_id]
        )
        DismissAiReviewIssue(repository).execute(self.project.id, entry_id)
        if had_ai_issue:
            repository.record_translation_operation(
                self.project.id,
                previous_entries,
                previous_issues,
                "Dismiss AI review issue",
            )
        self.project.dirty = True

    def dismiss_ai_review_issues(self, entry_ids: Sequence[str]) -> int:
        repository = self._repository()
        previous_entries, previous_issues = self._operation_snapshot(
            repository, entry_ids
        )
        affected_entry_ids = tuple(
            entry_id
            for entry_id, issues in previous_issues.items()
            if any(issue.code is ValidationCode.AI_REVIEW for issue in issues)
        )
        dismissed_count = DismissAiReviewIssues(repository).execute(
            self.project.id, entry_ids
        )
        if dismissed_count:
            self._record_operation_for_updated_entries(
                repository,
                affected_entry_ids,
                previous_entries,
                previous_issues,
                "Dismiss AI review issues",
            )
            self.project.dirty = True
        return dismissed_count

    def set_entry_approval(self, entry_id: str, approved: bool) -> TranslationEntry:
        repository = self._repository()
        previous_entries, previous_issues = self._operation_snapshot(
            repository, (entry_id,)
        )
        entry = SetEntryApproval(repository).execute(
            self.project.id, entry_id, approved
        )
        repository.record_translation_operation(
            self.project.id,
            previous_entries,
            previous_issues,
            "Approve translation" if approved else "Reopen translation",
        )
        self._reload(repository)
        if approved:
            self._store_approved_translation_memory_record(entry)
        return entry

    def set_entry_locked(self, entry_id: str, locked: bool) -> TranslationEntry:
        repository = self._repository()
        previous_entries, previous_issues = self._operation_snapshot(
            repository, (entry_id,)
        )
        entry = SetEntryLocked(repository).execute(self.project.id, entry_id, locked)
        repository.record_translation_operation(
            self.project.id,
            previous_entries,
            previous_issues,
            "Lock translation" if locked else "Unlock translation",
        )
        self._reload(repository)
        return entry

    def set_entries_approval(
        self, entry_ids: Sequence[str], approved: bool
    ) -> tuple[str, ...]:
        repository = self._repository()
        previous_entries, previous_issues = self._operation_snapshot(
            repository, entry_ids
        )
        updated_entry_ids = SetEntriesApproval(repository).execute(
            self.project.id, entry_ids, approved
        )
        self._record_operation_for_updated_entries(
            repository,
            updated_entry_ids,
            previous_entries,
            previous_issues,
            "Approve translations" if approved else "Reopen translations",
        )
        self._reload(repository)
        if approved:
            for entry_id in updated_entry_ids:
                self._store_approved_translation_memory_record(
                    self.project.get_entry(entry_id)
                )
        return updated_entry_ids

    def _store_approved_translation_memory_record(self, entry: TranslationEntry) -> None:
        if self._translation_memory is None or entry.translation is None:
            return
        self._translation_memory.store(
            TranslationMemoryRecord(
                self.project.source_language,
                self.project.target_language,
                entry.source,
                entry.translation,
                entry.context or "",
            )
        )

    def set_entries_locked(
        self, entry_ids: Sequence[str], locked: bool
    ) -> tuple[str, ...]:
        repository = self._repository()
        previous_entries, previous_issues = self._operation_snapshot(
            repository, entry_ids
        )
        updated_entry_ids = SetEntriesLocked(repository).execute(
            self.project.id, entry_ids, locked
        )
        self._record_operation_for_updated_entries(
            repository,
            updated_entry_ids,
            previous_entries,
            previous_issues,
            "Lock translations" if locked else "Unlock translations",
        )
        self._reload(repository)
        return updated_entry_ids

    def _operation_snapshot(
        self,
        repository: ProjectRepository,
        entry_ids: Sequence[str],
    ) -> tuple[tuple[TranslationEntry, ...], dict[str, tuple[ValidationIssue, ...]]]:
        selected_ids = tuple(dict.fromkeys(entry_ids))
        entries = tuple(
            repository.get_entry(self.project.id, entry_id)
            for entry_id in selected_ids
        )
        selected = set(selected_ids)
        issues: dict[str, list[ValidationIssue]] = {
            entry_id: [] for entry_id in selected_ids
        }
        for issue in repository.list_validation_issues(self.project.id):
            if issue.entry_id in selected:
                issues[issue.entry_id].append(
                    ValidationIssue(issue.code, issue.message)
                )
        return entries, {
            entry_id: tuple(entry_issues)
            for entry_id, entry_issues in issues.items()
        }

    def _record_operation_for_updated_entries(
        self,
        repository: ProjectRepository,
        updated_entry_ids: Sequence[str],
        previous_entries: Sequence[TranslationEntry],
        previous_issues: Mapping[str, Sequence[ValidationIssue]],
        label: str,
    ) -> None:
        updated = set(updated_entry_ids)
        repository.record_translation_operation(
            self.project.id,
            tuple(entry for entry in previous_entries if entry.id in updated),
            previous_issues,
            label,
        )

    def entry_revisions(
        self, entry_id: str, limit: int = 50
    ) -> tuple[EntryRevision, ...]:
        return self._repository().list_entry_revisions(
            self.project.id, entry_id, limit
        )

    def project_operations(self, limit: int = 50) -> tuple[ProjectOperation, ...]:
        return self._repository().list_translation_operations(self.project.id, limit)

    def restore_entry_revision(
        self, entry_id: str, revision_id: int
    ) -> TranslationEntry:
        repository = self._repository()
        previous_entries, previous_issues = self._operation_snapshot(
            repository, (entry_id,)
        )
        entry = RestoreEntryRevision(
            repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        ).execute(self.project.id, entry_id, revision_id)
        repository.record_translation_operation(
            self.project.id,
            previous_entries,
            previous_issues,
            "Restore translation revision",
        )
        self._replace_entry(entry)
        return entry

    def translation_memory_match(
        self, entry_id: str
    ) -> TranslationMemoryRecord | None:
        if self._translation_memory is None:
            return None
        repository = self._repository()
        return FindTranslationMemoryMatch(
            repository, self._translation_memory
        ).execute(self.project.id, entry_id)

    def translation_memory_matches(
        self,
        entry_id: str,
        limit: int = 5,
        minimum_score: float = 0.6,
    ) -> tuple[TranslationMemoryMatch, ...]:
        if self._translation_memory is None:
            return ()
        repository = self._repository()
        return FindTranslationMemoryMatches(
            repository, self._translation_memory
        ).execute(self.project.id, entry_id, limit, minimum_score)

    def translation_memory_records(
        self, source_language: str = "", target_language: str = "", search: str = ""
    ) -> tuple[TranslationMemoryRecord, ...]:
        if self._translation_memory is None:
            return ()
        return self._translation_memory.list_records(
            source_language, target_language, search
        )

    def store_translation_memory_record(self, record: TranslationMemoryRecord) -> None:
        if self._translation_memory is None:
            raise RuntimeError("Translation memory is not configured")
        self._translation_memory.store(record)

    def delete_translation_memory_record(self, record: TranslationMemoryRecord) -> None:
        if self._translation_memory is None:
            raise RuntimeError("Translation memory is not configured")
        self._translation_memory.delete(record)

    def glossary_terms(self) -> tuple[GlossaryTerm, ...]:
        if self._glossary is None:
            return ()
        return self._glossary.list_terms(
            self.project.source_language,
            self.project.target_language,
        )

    def store_glossary_term(
        self,
        source: str,
        target: str,
        case_sensitive: bool = False,
    ) -> GlossaryTerm:
        if self._glossary is None:
            raise RuntimeError("No glossary is configured")
        term = GlossaryTerm(
            self.project.source_language,
            self.project.target_language,
            source,
            target,
            case_sensitive,
        )
        self._glossary.store(term)
        return term

    def remove_glossary_term(self, term: GlossaryTerm) -> None:
        if self._glossary is None:
            raise RuntimeError("No glossary is configured")
        if (
            term.source_language != self.project.source_language
            or term.target_language != self.project.target_language
        ):
            raise ValueError("Glossary term belongs to another language pair")
        self._glossary.remove(term)

    def import_glossary_csv(self, path: Path) -> int:
        if self._glossary is None or self._glossary_csv_format is None:
            raise RuntimeError("Glossary CSV support is not configured")
        terms = self._glossary_csv_format.import_file(
            path,
            self.project.source_language,
            self.project.target_language,
        )
        for term in terms:
            self._glossary.store(term)
        return len(terms)

    def export_glossary_csv(self, path: Path) -> None:
        if self._glossary_csv_format is None:
            raise RuntimeError("Glossary CSV support is not configured")
        self._glossary_csv_format.export_file(self.glossary_terms(), path)

    def save(self, destination: Path | None = None) -> Project:
        project = SaveProjectFile(
            self._project_container, self._repository_factory
        ).execute(self.session, destination)
        self._project = project
        return project

    def autosave(self) -> None:
        if self.session.container_path is None:
            raise ValueError("A destination is required for a project that has not been saved")
        repository = self._repository()
        repository.mark_project_saved(self.project.id)
        self._project_container.save_snapshot(self.session, self.session.container_path)

    def refresh_after_autosave(self) -> None:
        self._reload(self._repository())

    def export_json(self, destination: Path) -> None:
        ExportProjectJson(self._json_exporter, self._repository_factory).execute(
            self.session, destination
        )

    def export_po(self, destination: Path) -> None:
        if self._po_exporter is None:
            raise RuntimeError("PO export support is not configured")
        ExportProjectPo(self._po_exporter, self._repository_factory).execute(
            self.session, destination
        )

    def export_csv(self, destination: Path) -> None:
        if self._csv_exporter is None:
            raise RuntimeError("CSV export support is not configured")
        ExportProjectCsv(self._csv_exporter, self._repository_factory).execute(
            self.session, destination
        )

    def export_xml(self, destination: Path) -> None:
        if self._xml_exporter is None:
            raise RuntimeError("XML export support is not configured")
        ExportProjectXml(self._xml_exporter, self._repository_factory).execute(
            self.session, destination
        )

    def export_all_documents(self, destination_directory: Path) -> tuple[Path, ...]:
        """Export every project document using its original format and relative path."""
        return self.export_documents(
            tuple(document.id for document in self.project.documents), destination_directory
        )

    def export_documents(
        self, document_ids: Sequence[str] | set[str] | frozenset[str], destination_directory: Path
    ) -> tuple[Path, ...]:
        """Export selected documents using their original formats and relative paths."""
        selected_ids = frozenset(document_ids)
        if not selected_ids:
            raise ValueError("Select at least one project file to export")
        known_ids = {document.id for document in self.project.documents}
        unknown_ids = selected_ids - known_ids
        if unknown_ids:
            raise ValueError("One or more selected project files do not exist")
        destination_directory.parent.mkdir(parents=True, exist_ok=True)
        exported_relative_paths: list[Path] = []
        with tempfile.TemporaryDirectory(
            prefix=".locaforge-export-", dir=destination_directory.parent
        ) as temporary_name:
            temporary_directory = Path(temporary_name)
            for document in self.project.documents:
                if document.id not in selected_ids:
                    continue
                relative_path = Path(document.source_path)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError(
                        f"Document {document.name!r} has an unsafe export path"
                    )
                document_project = Project(
                    id=self.project.id,
                    name=document.name,
                    source_language=self.project.source_language,
                    target_language=self.project.target_language,
                    entries=[
                        entry
                        for entry in self.project.entries
                        if entry.document_id == document.id
                    ],
                    source_document=document.source_document,
                    model_settings=self.project.model_settings,
                    documents=[document],
                )
                staged_path = temporary_directory / relative_path
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                self._export_document(document_project, document.source_format, staged_path)
                exported_relative_paths.append(relative_path)

            destination_directory.mkdir(parents=True, exist_ok=True)
            for relative_path in exported_relative_paths:
                staged_path = temporary_directory / relative_path
                destination_path = destination_directory / relative_path
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged_path, destination_path)
        return tuple(destination_directory / path for path in exported_relative_paths)

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

    @property
    def source_format(self) -> str | None:
        source_format = self.session.metadata.get("source_format")
        if isinstance(source_format, str):
            return source_format
        source_file = self.session.metadata.get("source_file")
        if isinstance(source_file, str):
            suffix = Path(source_file).suffix.lower().lstrip(".")
            return suffix or None
        return None

    def export_preflight(self) -> ExportPreflight:
        entries_with_issues = {issue.entry_id for issue in self.validation_issues()}
        return ExportPreflight(
            untranslated_entries=sum(
                entry.translation is None for entry in self.project.entries
            ),
            entries_with_issues=len(entries_with_issues),
        )

    def project_statistics(self) -> ProjectStatistics:
        entries = self.project.entries
        entries_with_issues = {issue.entry_id for issue in self.validation_issues()}
        return ProjectStatistics(
            total_entries=len(entries),
            untranslated_entries=sum(
                entry.status is EntryStatus.UNTRANSLATED for entry in entries
            ),
            translated_entries=sum(entry.translation is not None for entry in entries),
            needs_review_entries=sum(
                entry.status is EntryStatus.NEEDS_REVIEW for entry in entries
            ),
            approved_entries=sum(
                entry.status is EntryStatus.APPROVED for entry in entries
            ),
            error_entries=sum(entry.status is EntryStatus.ERROR for entry in entries),
            locked_entries=sum(entry.locked for entry in entries),
            entries_with_issues=len(entries_with_issues),
        )

    def list_models(self) -> tuple[str, ...]:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        return self._llm_client.list_models()

    def ollama_health_check(self) -> bool:
        if self._llm_client is None:
            return False
        return self._llm_client.health_check()

    def set_llm_client(self, llm_client: LLMClient) -> None:
        """Replace the configured local backend (for example after changing its URL)."""
        self._llm_client = llm_client

    def pull_model(self, model: str) -> None:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        self._llm_client.pull_model(model)

    def update_model_settings(self, settings: ModelSettings) -> Project:
        repository = self._repository()
        self._project = UpdateModelSettings(repository).execute(self.project.id, settings)
        return self._project

    def set_model_settings_override_enabled(self, enabled: bool) -> Project:
        repository = self._repository()
        project = repository.get(self.project.id)
        if enabled and not project.model_settings_override_enabled:
            project.update_model_settings(self.resolve_model_settings(project))
        project.set_model_settings_override_enabled(enabled)
        repository.save(project)
        self._project = project
        return project

    def validation_issues(self) -> tuple[EntryValidationIssue, ...]:
        repository = self._repository()
        return repository.list_validation_issues(self.project.id)

    def validate_project(self) -> ProjectValidationResult:
        repository = self._repository()
        result = ValidateProject(repository, glossary=self._glossary).execute(
            self.project.id
        )
        self._reload(repository)
        return result

    def untranslated_entry_ids(self) -> tuple[str, ...]:
        return tuple(
            entry.id
            for entry in self.project.entries
            if entry.status is EntryStatus.UNTRANSLATED and not entry.locked
        )

    def reviewable_entry_ids(self) -> tuple[str, ...]:
        return tuple(
            entry.id
            for entry in self.project.entries
            if entry.status is EntryStatus.NEEDS_REVIEW
            and entry.translation is not None
            and not entry.locked
        )

    def translate_entries(
        self,
        entry_ids: Sequence[str],
        model: str | None = None,
        progress_callback: ProgressCallback | None = None,
        cancellation_check: CancellationCheck | None = None,
    ) -> BatchResult:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        repository = self._repository()
        previous_entries = {
            entry_id: repository.get_entry(self.project.id, entry_id)
            for entry_id in entry_ids
        }
        previous_issues: dict[str, list[ValidationIssue]] = {}
        for issue in repository.list_validation_issues(self.project.id):
            if issue.entry_id in previous_entries:
                previous_issues.setdefault(issue.entry_id, []).append(
                    ValidationIssue(issue.code, issue.message)
                )
        settings = self.resolve_model_settings()
        selected_model = model or settings.model
        translated_entry_ids: list[str] = []
        skipped_entry_ids: list[str] = []
        errors: list[str] = []
        report_progress = progress_callback or _ignore_progress
        is_cancelled = cancellation_check or _never_cancel
        total_entries = len(entry_ids)
        completed_entries = 0
        cancelled = False
        report_progress(completed_entries, total_entries)
        for offset in range(0, len(entry_ids), settings.batch_size):
            if is_cancelled():
                cancelled = True
                break
            batch_entry_ids = entry_ids[offset : offset + settings.batch_size]
            result = TranslateBatch(
                repository,
                self._llm_client,
                translation_memory=self._translation_memory,
                glossary=self._glossary,
            ).execute(
                self.project.id,
                batch_entry_ids,
                selected_model,
                settings.timeout_seconds,
                settings.system_prompt,
                is_cancelled,
                settings.translation_reasoning,
            )
            translated_entry_ids.extend(result.translated_entry_ids)
            skipped_entry_ids.extend(result.skipped_entry_ids)
            errors.extend(result.errors)
            if result.cancelled:
                completed_entries += len(result.translated_entry_ids) + len(
                    result.skipped_entry_ids
                )
                report_progress(completed_entries, total_entries)
                cancelled = True
                break
            completed_entries += len(batch_entry_ids)
            report_progress(completed_entries, total_entries)
        changed_entry_ids = tuple(dict.fromkeys(translated_entry_ids))
        repository.record_translation_operation(
            self.project.id,
            tuple(previous_entries[entry_id] for entry_id in changed_entry_ids),
            previous_issues,
            "Translate entries",
        )
        self._reload(repository)
        return BatchResult(
            tuple(translated_entry_ids),
            tuple(skipped_entry_ids),
            tuple(errors),
            cancelled,
        )

    def can_undo_last_translation(self) -> bool:
        return self._repository().has_undoable_translation_operation(self.project.id)

    def next_undo_operation_label(self) -> str | None:
        return self._repository().next_undo_operation_label(self.project.id)

    def undo_last_translation(self) -> tuple[TranslationEntry, ...]:
        repository = self._repository()
        restored = repository.undo_last_translation_operation(self.project.id)
        if not restored:
            raise ValueError("There is no translation operation to undo")
        self._reload(repository)
        return restored

    def can_redo_last_translation(self) -> bool:
        return self._repository().has_redoable_translation_operation(self.project.id)

    def next_redo_operation_label(self) -> str | None:
        return self._repository().next_redo_operation_label(self.project.id)

    def redo_last_translation(self) -> tuple[TranslationEntry, ...]:
        repository = self._repository()
        restored = repository.redo_last_translation_operation(self.project.id)
        if not restored:
            raise ValueError("There is no translation operation to redo")
        self._reload(repository)
        return restored

    def _repository(self) -> ProjectRepository:
        return self._repository_factory.create(self.session.database_path)

    def _reload(self, repository: ProjectRepository) -> None:
        self._project = repository.get(self.project.id)

    def _replace_entry(self, updated_entry: TranslationEntry) -> None:
        for index, entry in enumerate(self.project.entries):
            if entry.id == updated_entry.id:
                self.project.entries[index] = updated_entry
                self.project.dirty = True
                return
        raise KeyError(f"Entry {updated_entry.id!r} was not found in the open project")

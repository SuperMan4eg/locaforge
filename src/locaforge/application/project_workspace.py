"""Stateful application facade used by desktop presentation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from locaforge.application.dto.model_performance import ModelPerformanceSnapshot
from locaforge.application.dto.project import (
    DocumentRefreshPreview,
    ExportPreflight,
    ProjectStatistics,
)
from locaforge.application.dto.review import ReviewBatchResult
from locaforge.application.dto.translation import BatchResult
from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ProjectValidationResult,
)
from locaforge.application.errors import NoOpenProjectError
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
from locaforge.application.ports.llm import LLMClient, ModelPerformanceProvider
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
from locaforge.application.services.batch_translation import BatchTranslationService
from locaforge.application.services.document_refresh import (
    DocumentRefreshPlan,
    DocumentRefreshService,
)
from locaforge.application.services.document_refresh import (
    ImportFieldMapping as ImportFieldMapping,
)
from locaforge.application.services.document_workspace import DocumentWorkspaceService
from locaforge.application.services.entry_state import EntryStateService
from locaforge.application.services.model_configuration import ModelConfigurationService
from locaforge.application.services.project_creation import ProjectCreationService
from locaforge.application.services.project_export import ProjectExportService
from locaforge.application.services.project_history import ProjectHistoryService
from locaforge.application.services.project_persistence import ProjectPersistenceService
from locaforge.application.services.project_profile import ProjectProfileService
from locaforge.application.services.project_reporting import ProjectReportingService
from locaforge.application.services.project_validation import ProjectValidationService
from locaforge.application.services.review_issues import ReviewIssueService
from locaforge.application.services.source_import import SourceImportService
from locaforge.application.services.terminology import TerminologyService
from locaforge.application.services.translation_editing import TranslationEditingService
from locaforge.application.services.translation_review import TranslationReviewService
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import TranslationEntry
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
        self._llm_client = llm_client
        self._project_container = project_container
        self._repository_factory = repository_factory
        self._translation_memory = translation_memory
        self._glossary = glossary
        self._glossary_csv_format = glossary_csv_format
        self._terminology = TerminologyService(
            translation_memory, glossary, glossary_csv_format
        )
        self._batch_translation = BatchTranslationService(
            llm_client, translation_memory, glossary
        )
        self._translation_review = TranslationReviewService(llm_client)
        self._model_configuration = ModelConfigurationService(llm_client)
        self._project_profiles = ProjectProfileService(
            llm_client, project_metadata_lookup
        )
        self._project_creation = ProjectCreationService(
            project_container, repository_factory
        )
        self._source_import = SourceImportService(
            json_importer,
            project_container,
            repository_factory,
            csv_importer,
            po_importer,
            xml_importer,
        )
        self._project_persistence = ProjectPersistenceService(
            project_container, repository_factory
        )
        self._project_export = ProjectExportService(
            json_exporter,
            repository_factory,
            po_exporter,
            csv_exporter,
            xml_exporter,
        )
        self._translation_editing = TranslationEditingService(
            translation_memory, glossary
        )
        self._entry_state = EntryStateService(translation_memory)
        self._review_issues = ReviewIssueService()
        self._history = ProjectHistoryService()
        self._validation = ProjectValidationService(glossary)
        self._project: Project | None = None
        self._session: ProjectSession | None = None

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
        return self._model_configuration.global_settings

    def set_global_model_settings(self, settings: ModelSettings) -> None:
        """Set application-wide settings used by projects without an override."""
        self._model_configuration.set_global_settings(settings)

    def resolve_model_settings(self, project: Project | None = None) -> ModelSettings:
        """Return the effective model settings for a project or the application."""
        target = project if project is not None else self._project
        return self._model_configuration.resolve(target)

    @property
    def model_settings_source(self) -> str:
        return self._model_configuration.source(self.project)

    def create_from_json(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: JsonFieldMapping | None = None,
    ) -> Project:
        created = self._source_import.create_from_json(
            source_path, destination, source_language, target_language, field_mapping
        )
        self._project = created.project
        self._session = created.session
        return self._project

    def generate_project_profile(
        self, name: str, *, use_online_lookup: bool = False
    ) -> ProjectProfile:
        return self._project_profiles.generate(
            name,
            self.resolve_model_settings(),
            use_online_lookup=use_online_lookup,
        )

    def create_project(
        self,
        destination: Path,
        name: str,
        source_language: str,
        target_language: str,
        profile: ProjectProfile | None = None,
    ) -> Project:
        """Create and open an empty project before any source files are imported."""
        created = self._project_creation.create(
            destination, name, source_language, target_language, profile
        )
        self._project = created.project
        self._session = created.session
        return created.project

    def import_files(
        self,
        source_paths: Sequence[Path],
        field_mappings: Mapping[Path, ImportFieldMapping] | None = None,
        document_paths: Mapping[Path, str] | None = None,
    ) -> tuple[ProjectDocument, ...]:
        """Import one or more source files into the currently open project."""
        return self._source_import.add_files(
            self._repository(),
            self.session,
            self.project,
            source_paths,
            field_mappings,
            document_paths,
        )

    def update_project_profile(
        self,
        name: str,
        source_language: str,
        target_language: str,
        profile: ProjectProfile,
    ) -> None:
        """Update project-owned metadata and persist it in the working database."""
        ProjectProfileService.update(
            self._repository(),
            self.session,
            self.project,
            name,
            source_language,
            target_language,
            profile,
        )

    def remove_documents(self, document_ids: Sequence[str]) -> tuple[int, int]:
        """Remove documents and their project-owned data, never source files."""
        repository = self._repository()
        result = DocumentWorkspaceService().remove(
            repository,
            self.project,
            document_ids,
        )
        self._project = result.project
        DocumentWorkspaceService.sync_source_metadata(
            self.project,
            self.session.metadata,
        )
        return result.removed_documents, result.removed_entries

    def preview_document_refresh(
        self, document_ids: Sequence[str]
    ) -> DocumentRefreshPreview:
        return self._prepare_document_refresh(document_ids).preview

    def refresh_documents(
        self, document_ids: Sequence[str]
    ) -> DocumentRefreshPreview:
        plan = self._prepare_document_refresh(document_ids)
        repository = self._repository()
        self._project = DocumentWorkspaceService().apply_refresh(
            repository,
            self.project,
            plan,
        )
        return plan.preview

    def _prepare_document_refresh(
        self, document_ids: Sequence[str]
    ) -> DocumentRefreshPlan:
        return DocumentRefreshService().prepare(
            self.project,
            document_ids,
            self._source_import.import_file,
        )

    def inspect_json_fields(self, path: Path) -> tuple[str, ...]:
        return self._source_import.inspect_json_fields(path)

    def inspect_csv_fields(self, path: Path) -> tuple[str, ...]:
        return self._source_import.inspect_csv_fields(path)

    def create_from_csv(
        self,
        source_path: Path,
        destination: Path,
        source_language: str,
        target_language: str,
        field_mapping: CsvFieldMapping,
    ) -> Project:
        created = self._source_import.create_from_csv(
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
        created = self._source_import.create_from_po(
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
        created = self._source_import.create_from_xml(
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
        created = self._source_import.create_from_files(
            source_paths,
            destination,
            source_language,
            target_language,
            field_mappings,
        )
        self._project = created.project
        self._session = created.session
        return created.project

    def inspect_xml_attribute_names(self, path: Path) -> tuple[str, ...]:
        return self._source_import.inspect_xml_attribute_names(path)

    def open(self, path: Path) -> Project:
        opened = self._project_persistence.open(path)
        self._project = opened.project
        self._session = opened.session
        return self._project

    @staticmethod
    def backup_path(path: Path) -> Path:
        return ProjectPersistenceService.backup_path(path)

    def open_backup(self, original_path: Path) -> Project:
        """Open the automatic backup as an unsaved recovery copy."""
        opened = self._project_persistence.open_backup(original_path)
        self._project = opened.project
        self._session = opened.session
        return self._project

    def edit_translation(self, entry_id: str, translation: str | None) -> TranslationEntry:
        repository = self._repository()
        entry = self._translation_editing.edit(
            repository, self.project, entry_id, translation
        )
        self._replace_entry(entry)
        return entry

    def select_translation_candidate(
        self, entry_id: str, candidate: str
    ) -> TranslationEntry:
        entry = self._translation_editing.select_candidate(
            self._repository(), self.project, entry_id, candidate
        )
        self._replace_entry(entry)
        return entry

    def replace_translations(
        self, search_text: str, replacement_text: str
    ) -> tuple[str, ...]:
        repository = self._repository()
        updated_entry_ids = self._translation_editing.replace(
            repository, self.project, search_text, replacement_text
        )
        self._reload(repository)
        return updated_entry_ids

    def matching_translation_entry_ids(self, entry_id: str) -> tuple[str, ...]:
        return self._translation_editing.matching_entry_ids(
            self._repository(), self.project, entry_id
        )

    def apply_translation_to_matches(
        self, entry_id: str, translation: str
    ) -> tuple[str, ...]:
        repository = self._repository()
        updated_entry_ids = self._translation_editing.apply_to_matches(
            repository, self.project, entry_id, translation
        )
        self._reload(repository)
        return updated_entry_ids

    def review_entries(
        self,
        entry_ids: Sequence[str],
        progress_callback: ProgressCallback | None = None,
        cancellation_check: CancellationCheck | None = None,
    ) -> ReviewBatchResult:
        repository = self._repository()
        run = self._translation_review.review(
            repository,
            self.project,
            entry_ids,
            self.resolve_model_settings(),
            progress_callback,
            cancellation_check,
        )
        if run.project_changed:
            self._reload(repository)
        return run.result

    def dismiss_ai_review_issue(self, entry_id: str) -> None:
        self._review_issues.dismiss_one(
            self._repository(), self.project, entry_id
        )
        self.project.dirty = True

    def dismiss_ai_review_issues(self, entry_ids: Sequence[str]) -> int:
        dismissed_count = self._review_issues.dismiss_many(
            self._repository(), self.project, entry_ids
        )
        if dismissed_count:
            self.project.dirty = True
        return dismissed_count

    def set_entry_approval(self, entry_id: str, approved: bool) -> TranslationEntry:
        repository = self._repository()
        entry = self._entry_state.set_approval(
            repository, self.project, entry_id, approved
        )
        self._reload(repository)
        return entry

    def set_entry_locked(self, entry_id: str, locked: bool) -> TranslationEntry:
        repository = self._repository()
        entry = self._entry_state.set_locked(
            repository, self.project, entry_id, locked
        )
        self._reload(repository)
        return entry

    def set_entries_approval(
        self, entry_ids: Sequence[str], approved: bool
    ) -> tuple[str, ...]:
        repository = self._repository()
        updated_entry_ids = self._entry_state.set_approvals(
            repository, self.project, entry_ids, approved
        )
        self._reload(repository)
        return updated_entry_ids

    def set_entries_locked(
        self, entry_ids: Sequence[str], locked: bool
    ) -> tuple[str, ...]:
        repository = self._repository()
        updated_entry_ids = self._entry_state.set_locks(
            repository, self.project, entry_ids, locked
        )
        self._reload(repository)
        return updated_entry_ids

    def entry_revisions(
        self, entry_id: str, limit: int = 50
    ) -> tuple[EntryRevision, ...]:
        return self._history.entry_revisions(
            self._repository(), self.project.id, entry_id, limit
        )

    def project_operations(self, limit: int = 50) -> tuple[ProjectOperation, ...]:
        return self._history.operations(
            self._repository(), self.project.id, limit
        )

    def restore_entry_revision(
        self, entry_id: str, revision_id: int
    ) -> TranslationEntry:
        repository = self._repository()
        entry = self._history.restore_revision(
            repository,
            self.project,
            entry_id,
            revision_id,
            self._translation_memory,
            self._glossary,
        )
        self._replace_entry(entry)
        return entry

    def translation_memory_match(
        self, entry_id: str
    ) -> TranslationMemoryRecord | None:
        return self._terminology.translation_memory_match(
            self._repository(), self.project, entry_id
        )

    def translation_memory_matches(
        self,
        entry_id: str,
        limit: int = 5,
        minimum_score: float = 0.6,
    ) -> tuple[TranslationMemoryMatch, ...]:
        return self._terminology.translation_memory_matches(
            self._repository(), self.project, entry_id, limit, minimum_score
        )

    def translation_memory_records(
        self, source_language: str = "", target_language: str = "", search: str = ""
    ) -> tuple[TranslationMemoryRecord, ...]:
        return self._terminology.translation_memory_records(
            source_language, target_language, search
        )

    def store_translation_memory_record(self, record: TranslationMemoryRecord) -> None:
        self._terminology.store_translation_memory_record(record)

    def delete_translation_memory_record(self, record: TranslationMemoryRecord) -> None:
        self._terminology.delete_translation_memory_record(record)

    def glossary_terms(self) -> tuple[GlossaryTerm, ...]:
        return self._terminology.glossary_terms(self.project)

    def store_glossary_term(
        self,
        source: str,
        target: str,
        case_sensitive: bool = False,
    ) -> GlossaryTerm:
        return self._terminology.store_glossary_term(
            self.project, source, target, case_sensitive
        )

    def remove_glossary_term(self, term: GlossaryTerm) -> None:
        self._terminology.remove_glossary_term(self.project, term)

    def import_glossary_csv(self, path: Path) -> int:
        return self._terminology.import_glossary_csv(self.project, path)

    def export_glossary_csv(self, path: Path) -> None:
        self._terminology.export_glossary_csv(self.project, path)

    def save(self, destination: Path | None = None) -> Project:
        project = self._project_persistence.save(self.session, destination)
        self._project = project
        return project

    def autosave(self) -> None:
        self._project_persistence.autosave(
            self._repository(), self.session, self.project
        )

    def refresh_after_autosave(self) -> None:
        self._project_persistence.refresh_dirty_state(
            self._repository(), self.project
        )

    def export_json(self, destination: Path) -> None:
        self._project_export.export_json(self.session, destination)

    def export_po(self, destination: Path) -> None:
        self._project_export.export_po(self.session, destination)

    def export_csv(self, destination: Path) -> None:
        self._project_export.export_csv(self.session, destination)

    def export_xml(self, destination: Path) -> None:
        self._project_export.export_xml(self.session, destination)

    def export_all_documents(self, destination_directory: Path) -> tuple[Path, ...]:
        """Export every project document using its original format and relative path."""
        return self._project_export.export_all_documents(
            self.project, destination_directory
        )

    def export_documents(
        self, document_ids: Sequence[str] | set[str] | frozenset[str], destination_directory: Path
    ) -> tuple[Path, ...]:
        """Export selected documents using their original formats and relative paths."""
        return self._project_export.export_documents(
            self.project, document_ids, destination_directory
        )

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
        return ProjectReportingService().export_preflight(
            self.project,
            self.validation_issues(),
        )

    def project_statistics(self) -> ProjectStatistics:
        return ProjectReportingService().statistics(
            self.project,
            self.validation_issues(),
        )

    def list_models(self) -> tuple[str, ...]:
        return self._model_configuration.list_models()

    def ollama_health_check(self) -> bool:
        return self._model_configuration.health_check()

    def model_performance_snapshot(self) -> ModelPerformanceSnapshot:
        if isinstance(self._llm_client, ModelPerformanceProvider):
            return self._llm_client.performance_snapshot()
        return ModelPerformanceSnapshot()

    def set_llm_client(self, llm_client: LLMClient) -> None:
        """Replace the configured local backend (for example after changing its URL)."""
        self._llm_client = llm_client
        self._model_configuration.set_llm_client(llm_client)
        self._batch_translation.set_llm_client(llm_client)
        self._translation_review.set_llm_client(llm_client)
        self._project_profiles.set_llm_client(llm_client)

    def pull_model(self, model: str) -> None:
        self._model_configuration.pull_model(model)

    def update_model_settings(self, settings: ModelSettings) -> Project:
        repository = self._repository()
        self._project = self._model_configuration.update_project_settings(
            repository, self.project, settings
        )
        return self._project

    def set_model_settings_override_enabled(self, enabled: bool) -> Project:
        repository = self._repository()
        self._project = self._model_configuration.set_project_override(
            repository, self.project, enabled
        )
        return self._project

    def validation_issues(self) -> tuple[EntryValidationIssue, ...]:
        return self._validation.issues(self._repository(), self.project)

    def validate_project(self) -> ProjectValidationResult:
        repository = self._repository()
        result = self._validation.validate(repository, self.project)
        self._reload(repository)
        return result

    def untranslated_entry_ids(self) -> tuple[str, ...]:
        return self._validation.untranslated_entry_ids(self.project)

    def reviewable_entry_ids(self) -> tuple[str, ...]:
        return self._validation.reviewable_entry_ids(self.project)

    def translate_entries(
        self,
        entry_ids: Sequence[str],
        model: str | None = None,
        progress_callback: ProgressCallback | None = None,
        cancellation_check: CancellationCheck | None = None,
    ) -> BatchResult:
        repository = self._repository()
        settings = self.resolve_model_settings()
        result = self._batch_translation.translate(
            repository,
            self.project,
            entry_ids,
            settings,
            model,
            progress_callback,
            cancellation_check,
        )
        self._reload(repository)
        return result

    def can_undo_last_translation(self) -> bool:
        return self._history.can_undo(self._repository(), self.project.id)

    def next_undo_operation_label(self) -> str | None:
        return self._history.next_undo_label(
            self._repository(), self.project.id
        )

    def undo_last_translation(self) -> tuple[TranslationEntry, ...]:
        repository = self._repository()
        restored = self._history.undo(repository, self.project.id)
        self._reload(repository)
        return restored

    def can_redo_last_translation(self) -> bool:
        return self._history.can_redo(self._repository(), self.project.id)

    def next_redo_operation_label(self) -> str | None:
        return self._history.next_redo_label(
            self._repository(), self.project.id
        )

    def redo_last_translation(self) -> tuple[TranslationEntry, ...]:
        repository = self._repository()
        restored = self._history.redo(repository, self.project.id)
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

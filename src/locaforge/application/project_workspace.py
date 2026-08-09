"""Stateful application facade used by desktop presentation."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from locaforge.application.dto.project import ExportPreflight, ProjectStatistics
from locaforge.application.dto.review import ReviewBatchResult
from locaforge.application.dto.translation import BatchResult
from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ProjectValidationResult,
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
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.history import EntryRevision
from locaforge.domain.project import Project
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
            project.configure_single_document(path, "json")
            return project
        if suffix in {".csv", ".tsv"}:
            if self._csv_importer is None or not isinstance(field_mapping, CsvFieldMapping):
                raise ValueError(f"CSV field mapping is required for {path.name!r}")
            project = self._csv_importer.import_file(
                path, source_language, target_language, field_mapping
            )
            project.configure_single_document(path, "csv")
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
            project.configure_single_document(path, "xml")
            return project
        raise ValueError(f"Unsupported localization file format: {path.suffix or path.name}")

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

    def edit_translation(self, entry_id: str, translation: str | None) -> TranslationEntry:
        repository = self._repository()
        entry = EditTranslation(repository, glossary=self._glossary).execute(
            self.project.id, entry_id, translation
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
        updated_entry_ids = ReplaceTranslations(
            repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        ).execute(self.project.id, search_text, replacement_text)
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
        updated_entry_ids = ApplyTranslationToMatches(
            repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        ).execute(self.project.id, entry_id, translation)
        ValidateProject(repository, glossary=self._glossary).execute(self.project.id)
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
        settings = self.project.model_settings
        report_progress = progress_callback or _ignore_progress
        is_cancelled = cancellation_check or _never_cancel
        reviewed_entries = 0
        issue_count = 0
        report_progress(0, len(entry_ids))
        for offset in range(0, len(entry_ids), settings.batch_size):
            if is_cancelled():
                if reviewed_entries:
                    self._reload(repository)
                return ReviewBatchResult(reviewed_entries, issue_count, True)
            batch_entry_ids = entry_ids[offset : offset + settings.batch_size]
            issue_count += reviewer.execute(
                self.project.id,
                batch_entry_ids,
                settings.effective_review_model,
                settings.timeout_seconds,
                settings.review_prompt,
            )
            reviewed_entries += len(batch_entry_ids)
            report_progress(reviewed_entries, len(entry_ids))
        if reviewed_entries:
            self._reload(repository)
        return ReviewBatchResult(reviewed_entries, issue_count)

    def dismiss_ai_review_issue(self, entry_id: str) -> None:
        DismissAiReviewIssue(self._repository()).execute(self.project.id, entry_id)
        self.project.dirty = True

    def dismiss_ai_review_issues(self, entry_ids: Sequence[str]) -> int:
        dismissed_count = DismissAiReviewIssues(self._repository()).execute(
            self.project.id, entry_ids
        )
        if dismissed_count:
            self.project.dirty = True
        return dismissed_count

    def set_entry_approval(self, entry_id: str, approved: bool) -> TranslationEntry:
        repository = self._repository()
        entry = SetEntryApproval(repository).execute(
            self.project.id, entry_id, approved
        )
        self._reload(repository)
        if approved:
            self._store_approved_translation_memory_record(entry)
        return entry

    def set_entry_locked(self, entry_id: str, locked: bool) -> TranslationEntry:
        repository = self._repository()
        entry = SetEntryLocked(repository).execute(self.project.id, entry_id, locked)
        self._reload(repository)
        return entry

    def set_entries_approval(
        self, entry_ids: Sequence[str], approved: bool
    ) -> tuple[str, ...]:
        repository = self._repository()
        updated_entry_ids = SetEntriesApproval(repository).execute(
            self.project.id, entry_ids, approved
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
        updated_entry_ids = SetEntriesLocked(repository).execute(
            self.project.id, entry_ids, locked
        )
        self._reload(repository)
        return updated_entry_ids

    def entry_revisions(
        self, entry_id: str, limit: int = 50
    ) -> tuple[EntryRevision, ...]:
        return self._repository().list_entry_revisions(
            self.project.id, entry_id, limit
        )

    def restore_entry_revision(
        self, entry_id: str, revision_id: int
    ) -> TranslationEntry:
        repository = self._repository()
        entry = RestoreEntryRevision(
            repository,
            translation_memory=self._translation_memory,
            glossary=self._glossary,
        ).execute(self.project.id, entry_id, revision_id)
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
        destination_directory.parent.mkdir(parents=True, exist_ok=True)
        exported_relative_paths: list[Path] = []
        with tempfile.TemporaryDirectory(
            prefix=".locaforge-export-", dir=destination_directory.parent
        ) as temporary_name:
            temporary_directory = Path(temporary_name)
            for document in self.project.documents:
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

    def pull_model(self, model: str) -> None:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        self._llm_client.pull_model(model)

    def update_model_settings(self, settings: ModelSettings) -> Project:
        repository = self._repository()
        self._project = UpdateModelSettings(repository).execute(self.project.id, settings)
        return self._project

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
        settings = self.project.model_settings
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

    def undo_last_translation(self) -> tuple[TranslationEntry, ...]:
        repository = self._repository()
        restored = repository.undo_last_translation_operation(self.project.id)
        if not restored:
            raise ValueError("There is no translation operation to undo")
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

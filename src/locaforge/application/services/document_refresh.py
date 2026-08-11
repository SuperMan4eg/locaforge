"""Plan source-document refreshes without mutating the open project."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from locaforge.application.dto.project import DocumentRefreshPreview
from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project

type ImportFieldMapping = JsonFieldMapping | CsvFieldMapping | XmlFieldMapping | None
type SourceFileImporter = Callable[[Path, str, str, ImportFieldMapping], Project]


@dataclass(frozen=True, slots=True)
class DocumentRefreshPlan:
    documents: tuple[ProjectDocument, ...]
    entries: tuple[TranslationEntry, ...]
    preview: DocumentRefreshPreview
    removed_entry_ids: frozenset[str]
    changed_entry_ids: frozenset[str]


class DocumentRefreshService:
    """Re-import selected documents and preserve compatible project-owned state."""

    def prepare(
        self,
        project: Project,
        document_ids: Sequence[str],
        import_source_file: SourceFileImporter,
    ) -> DocumentRefreshPlan:
        selected_ids = tuple(dict.fromkeys(document_ids))
        if not selected_ids:
            raise ValueError("Select at least one project file to refresh")
        documents = [
            document for document in project.documents if document.id in selected_ids
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
                raise ValueError(
                    f"Source location is not recorded for {document.source_path!r}"
                )
            source_path = Path(document.source_location)
            if not source_path.is_file():
                raise ValueError(f"Source file no longer exists: {source_path}")
            mapping = self.restore_import_mapping(document)
            imported = import_source_file(
                source_path,
                project.source_language,
                project.target_language,
                mapping,
            )
            imported_document = imported.documents[0]
            imported_document.id = document.id
            imported_document.name = document.name
            imported_document.source_path = document.source_path
            imported_document.source_location = document.source_location
            imported_document.import_settings = dict(document.import_settings)
            old_entries = [
                entry for entry in project.entries if entry.document_id == document.id
            ]
            old_by_identity = {
                self.entry_identity(entry): entry for entry in old_entries
            }
            seen_identities: set[tuple[object, ...]] = set()
            for entry in imported.entries:
                identity = self.entry_identity(entry)
                if identity in seen_identities:
                    raise ValueError(
                        f"Duplicate entry identity in {document.source_path!r}"
                    )
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
            removed_entry_ids = {
                old_by_identity[identity].id for identity in removed
            }
            removed_ids.update(removed_entry_ids)
            removed_count += len(removed_entry_ids)
            refreshed_documents.append(imported_document)
        return DocumentRefreshPlan(
            tuple(refreshed_documents),
            tuple(refreshed_entries),
            DocumentRefreshPreview(
                len(documents),
                new_count,
                changed_count,
                removed_count,
                unchanged_count,
            ),
            frozenset(removed_ids),
            frozenset(changed_ids),
        )

    @staticmethod
    def entry_identity(entry: TranslationEntry) -> tuple[object, ...]:
        if entry.key and entry.key != entry.source:
            return "key", entry.key, entry.context
        return "path", *entry.key_path

    @staticmethod
    def restore_import_mapping(document: ProjectDocument) -> ImportFieldMapping:
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
            names = (
                tuple(str(name) for name in raw_names)
                if isinstance(raw_names, list)
                else ()
            )
            return XmlFieldMapping(names)
        if document.source_format == "po":
            return None
        raise ValueError(
            f"Unsupported project document format: {document.source_format!r}"
        )

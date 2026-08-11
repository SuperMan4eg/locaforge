"""Project document lifecycle operations backed by a project repository."""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from dataclasses import dataclass

from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.services.document_refresh import DocumentRefreshPlan
from locaforge.domain.project import Project


@dataclass(frozen=True, slots=True)
class DocumentRemovalResult:
    project: Project
    removed_documents: int
    removed_entries: int


class DocumentWorkspaceService:
    """Apply document mutations while keeping project metadata consistent."""

    def remove(
        self,
        repository: ProjectRepository,
        project: Project,
        document_ids: Sequence[str],
    ) -> DocumentRemovalResult:
        selected_ids = tuple(dict.fromkeys(document_ids))
        if not selected_ids:
            raise ValueError("Select at least one project file to remove")
        known_ids = {document.id for document in project.documents}
        if not set(selected_ids).issubset(known_ids):
            raise ValueError("One or more selected project files do not exist")
        entry_count = sum(
            entry.document_id in selected_ids for entry in project.entries
        )
        repository.remove_documents(project.id, selected_ids)
        updated = repository.get(project.id)
        updated.source_document = (
            updated.documents[0].source_document if updated.documents else None
        )
        return DocumentRemovalResult(updated, len(selected_ids), entry_count)

    def apply_refresh(
        self,
        repository: ProjectRepository,
        project: Project,
        plan: DocumentRefreshPlan,
    ) -> Project:
        selected_ids = {document.id for document in plan.documents}
        document_by_id = {document.id: document for document in plan.documents}
        project.documents = [
            document_by_id.get(document.id, document)
            for document in project.documents
        ]
        project.entries = [
            entry for entry in project.entries if entry.document_id not in selected_ids
        ]
        project.entries.extend(plan.entries)
        project.source_document = (
            project.documents[0].source_document if project.documents else None
        )
        project.dirty = True
        repository.remove_entry_artifacts(
            project.id,
            tuple(plan.removed_entry_ids),
            tuple(plan.changed_entry_ids),
        )
        repository.save(project)
        return project

    @staticmethod
    def sync_source_metadata(
        project: Project,
        metadata: MutableMapping[str, object],
    ) -> None:
        metadata["source_files"] = [
            document.source_path for document in project.documents
        ]
        metadata["source_format"] = (
            project.documents[0].source_format
            if len(project.documents) == 1
            else "multiple"
        )

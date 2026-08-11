from collections.abc import Sequence
from typing import cast

from locaforge.application.dto.project import DocumentRefreshPreview
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.services.document_refresh import DocumentRefreshPlan
from locaforge.application.services.document_workspace import DocumentWorkspaceService
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project


def make_document(document_id: str, name: str, source: object) -> ProjectDocument:
    return ProjectDocument(document_id, name, name, "json", source)


class FakeDocumentRepository:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.removed_artifacts: tuple[tuple[str, ...], tuple[str, ...]] | None = None
        self.saved_project: Project | None = None

    def remove_documents(
        self, project_id: str, document_ids: Sequence[str]
    ) -> None:
        assert project_id == self.project.id
        selected = set(document_ids)
        self.project.documents = [
            document
            for document in self.project.documents
            if document.id not in selected
        ]
        self.project.entries = [
            entry for entry in self.project.entries if entry.document_id not in selected
        ]

    def get(self, project_id: str) -> Project:
        assert project_id == self.project.id
        return self.project

    def remove_entry_artifacts(
        self,
        project_id: str,
        removed_entry_ids: Sequence[str],
        reset_validation_entry_ids: Sequence[str] = (),
    ) -> None:
        assert project_id == self.project.id
        self.removed_artifacts = (
            tuple(removed_entry_ids),
            tuple(reset_validation_entry_ids),
        )

    def save(self, project: Project) -> None:
        self.saved_project = project


def as_repository(repository: FakeDocumentRepository) -> ProjectRepository:
    return cast(ProjectRepository, repository)


def test_remove_returns_reloaded_project_and_counts_removed_entries() -> None:
    first = make_document("document-1", "first.json", {"first": "First"})
    second = make_document("document-2", "second.json", {"second": "Second"})
    project = Project(
        "project-1",
        "Game",
        "en",
        "ru",
        entries=[
            TranslationEntry("entry-1", ("first",), "First", document_id=first.id),
            TranslationEntry("entry-2", ("second",), "Second", document_id=second.id),
        ],
        documents=[first, second],
    )
    repository = FakeDocumentRepository(project)

    result = DocumentWorkspaceService().remove(
        as_repository(repository), project, (first.id, first.id)
    )

    assert result.removed_documents == 1
    assert result.removed_entries == 1
    assert [document.id for document in result.project.documents] == [second.id]
    assert result.project.source_document == second.source_document


def test_apply_refresh_replaces_selected_entries_and_cleans_artifacts() -> None:
    document = make_document("document-1", "strings.json", {"old": "Old"})
    project = Project(
        "project-1",
        "Game",
        "en",
        "ru",
        entries=[
            TranslationEntry("old", ("old",), "Old", document_id=document.id)
        ],
        documents=[document],
    )
    refreshed_document = make_document(
        document.id, document.name, {"new": "New"}
    )
    refreshed_entry = TranslationEntry(
        "new", ("new",), "New", document_id=document.id
    )
    plan = DocumentRefreshPlan(
        (refreshed_document,),
        (refreshed_entry,),
        DocumentRefreshPreview(1, 1, 0, 1, 0),
        frozenset({"old"}),
        frozenset(),
    )
    repository = FakeDocumentRepository(project)

    updated = DocumentWorkspaceService().apply_refresh(
        as_repository(repository), project, plan
    )

    assert updated.entries == [refreshed_entry]
    assert updated.dirty is True
    assert repository.removed_artifacts == (("old",), ())
    assert repository.saved_project is updated


def test_sync_source_metadata_handles_zero_one_and_multiple_documents() -> None:
    project = Project("project-1", "Game", "en", "ru")
    metadata: dict[str, object] = {}

    DocumentWorkspaceService.sync_source_metadata(project, metadata)
    assert metadata == {"source_files": [], "source_format": "multiple"}

    project.documents = [make_document("document-1", "one.json", {})]
    DocumentWorkspaceService.sync_source_metadata(project, metadata)
    assert metadata == {"source_files": ["one.json"], "source_format": "json"}

    project.documents.append(make_document("document-2", "two.json", {}))
    DocumentWorkspaceService.sync_source_metadata(project, metadata)
    assert metadata == {
        "source_files": ["one.json", "two.json"],
        "source_format": "multiple",
    }

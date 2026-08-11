from pathlib import Path

import pytest

from locaforge.application.services.document_refresh import DocumentRefreshService
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project


def make_document(document_id: str, source_path: Path) -> ProjectDocument:
    return ProjectDocument(
        id=document_id,
        name=source_path.name,
        source_path=source_path.name,
        source_format="json",
        source_document={},
        source_location=str(source_path),
    )


def test_prepare_preserves_unchanged_state_and_classifies_source_changes(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text("{}", encoding="utf-8")
    document = make_document("document-1", source_path)
    project = Project(
        "project-1",
        "Game",
        "en",
        "ru",
        entries=[
            TranslationEntry(
                "old-unchanged",
                ("unchanged",),
                "Same",
                "Перевод",
                EntryStatus.APPROVED,
                True,
                document_id=document.id,
            ),
            TranslationEntry(
                "old-changed",
                ("changed",),
                "Old source",
                "Старый перевод",
                EntryStatus.APPROVED,
                True,
                document_id=document.id,
            ),
            TranslationEntry(
                "old-removed",
                ("removed",),
                "Removed",
                document_id=document.id,
            ),
        ],
        documents=[document],
    )

    def import_source(
        path: Path, source_language: str, target_language: str, mapping: object
    ) -> Project:
        assert path == source_path
        assert (source_language, target_language, mapping) == ("en", "ru", None)
        imported_document = make_document("temporary", source_path)
        return Project(
            "imported",
            "Imported",
            "en",
            "ru",
            entries=[
                TranslationEntry("new-a", ("unchanged",), "Same"),
                TranslationEntry("new-b", ("changed",), "New source"),
                TranslationEntry("new-c", ("added",), "Added"),
            ],
            documents=[imported_document],
        )

    plan = DocumentRefreshService().prepare(
        project, (document.id,), import_source
    )

    by_path = {entry.key_path: entry for entry in plan.entries}
    unchanged = by_path[("unchanged",)]
    changed = by_path[("changed",)]
    assert unchanged.id == "old-unchanged"
    assert unchanged.status is EntryStatus.APPROVED
    assert unchanged.locked is True
    assert changed.id == "old-changed"
    assert changed.translation == "Старый перевод"
    assert changed.status is EntryStatus.NEEDS_REVIEW
    assert changed.locked is False
    assert plan.preview.new_entries == 1
    assert plan.preview.changed_entries == 1
    assert plan.preview.removed_entries == 1
    assert plan.preview.unchanged_entries == 1
    assert plan.changed_entry_ids == frozenset({"old-changed"})
    assert plan.removed_entry_ids == frozenset({"old-removed"})


def test_prepare_rejects_empty_and_unknown_document_selections(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text("{}", encoding="utf-8")
    document = make_document("document-1", source_path)
    project = Project(
        "project-1", "Game", "en", "ru", documents=[document]
    )
    service = DocumentRefreshService()

    with pytest.raises(ValueError, match="Select at least one project file"):
        service.prepare(project, (), lambda *_args: project)

    with pytest.raises(ValueError, match="selected project files do not exist"):
        service.prepare(project, ("missing",), lambda *_args: project)

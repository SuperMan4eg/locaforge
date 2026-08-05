from pathlib import Path

import pytest

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.errors import EntryNotFoundError, ProjectNotFoundError
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project
from locaforge.infrastructure.persistence.sqlite_project_repository import SQLiteProjectRepository


def make_project() -> Project:
    return Project(
        id="project-1",
        name="Dialog",
        source_language="en",
        target_language="ru",
        source_document={"dialog": ["Hello"]},
        entries=[
            TranslationEntry(
                id="entry-1",
                key_path=("dialog", 0),
                source="Hello",
                placeholders=("{name}",),
            )
        ],
    )


def test_create_and_get_restores_a_project(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()

    repository.create(project)

    assert repository.get(project.id) == project


def test_update_entry_persists_the_change_and_marks_project_dirty(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    repository.create(project)
    entry = project.set_entry_translation("entry-1", "Привет")

    repository.update_entry(project.id, entry)

    restored = repository.get(project.id)
    assert restored.entries[0].translation == "Привет"
    assert restored.entries[0].status is EntryStatus.NEEDS_REVIEW
    assert restored.dirty is True


def test_missing_objects_have_specific_errors(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")

    with pytest.raises(ProjectNotFoundError):
        repository.get("missing")
    with pytest.raises(EntryNotFoundError):
        repository.get_entry("missing", "entry-1")


def test_validation_issues_are_replaced_and_listed(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    repository.create(project)
    issue = ValidationIssue(
        ValidationCode.PLACEHOLDER_MISMATCH,
        "Translation must preserve placeholders",
    )

    repository.replace_validation_issues(project.id, "entry-1", (issue,))

    assert repository.list_validation_issues(project.id)[0].code is (
        ValidationCode.PLACEHOLDER_MISMATCH
    )
    repository.replace_validation_issues(project.id, "entry-1", ())
    assert not repository.list_validation_issues(project.id)


def test_bulk_validation_replacement_and_status_updates(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    repository.create(project)
    issue = ValidationIssue(ValidationCode.GLOSSARY_MISMATCH, "Use glossary term")
    entry = project.get_entry("entry-1")
    entry.mark_error()

    repository.replace_validation_issues_bulk(project.id, {entry.id: (issue,)})
    repository.update_entry_statuses(project.id, (entry,))

    assert repository.get_entry(project.id, entry.id).status is EntryStatus.ERROR
    assert repository.list_validation_issues(project.id)[0].code is (
        ValidationCode.GLOSSARY_MISMATCH
    )


def test_bulk_entry_update_records_translation_history(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    repository.create(project)
    entry = project.get_entry("entry-1")
    entry.set_translation("Updated")

    repository.update_entries(project.id, (entry,))

    assert repository.get_entry(project.id, entry.id).translation == "Updated"
    assert repository.list_entry_revisions(project.id, entry.id)[0].translation is None


def test_entry_translation_updates_create_ordered_history(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    repository.create(project)
    entry = project.set_entry_translation("entry-1", "Привет")
    repository.update_entry(project.id, entry)
    entry.set_translation("Здравствуйте")

    repository.update_entry(project.id, entry)

    revisions = repository.list_entry_revisions(project.id, entry.id)
    assert [revision.translation for revision in revisions] == ["Привет", None]
    assert repository.get_entry_revision(
        project.id, entry.id, revisions[0].revision_id
    ) == revisions[0]


def test_entry_history_survives_project_entry_rewrite(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    repository.create(project)
    entry = project.set_entry_translation("entry-1", "Привет")
    repository.update_entry(project.id, entry)

    repository.save(repository.get(project.id))

    assert repository.list_entry_revisions(project.id, entry.id)[0].translation is None

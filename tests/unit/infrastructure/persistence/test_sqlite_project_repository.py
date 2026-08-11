import json
import sqlite3
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


def test_opening_legacy_database_adds_document_support(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, source_language TEXT NOT NULL,
                target_language TEXT NOT NULL, source_document TEXT NOT NULL,
                model_settings TEXT NOT NULL DEFAULT '{}', dirty INTEGER NOT NULL
            );
            CREATE TABLE entries (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, row_order INTEGER NOT NULL,
                key_path TEXT NOT NULL, source TEXT NOT NULL, entry_key TEXT,
                translation TEXT, status TEXT NOT NULL, locked INTEGER NOT NULL,
                context TEXT, max_length INTEGER, placeholders TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("old", "Legacy", "en", "ru", json.dumps({"hello": "Hello"}), "{}", 0),
        )
        connection.execute(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "entry-1",
                "old",
                0,
                json.dumps(["hello"]),
                "Hello",
                None,
                None,
                "untranslated",
                0,
                None,
                None,
                "[]",
            ),
        )

    restored = SQLiteProjectRepository(database_path).get("old")

    assert restored.documents[0].source_format == "legacy"
    assert restored.entries[0].document_id == restored.documents[0].id
    assert restored.model_settings_override_enabled is True


def test_new_project_defaults_to_global_model_settings_mode(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()

    repository.create(project)

    assert repository.get(project.id).model_settings_override_enabled is False


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


def test_dirty_state_can_be_read_without_loading_the_project(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    repository.create(project)

    assert repository.is_project_dirty(project.id) is False

    repository.mark_project_dirty(project.id)

    assert repository.is_project_dirty(project.id) is True


def test_reading_dirty_state_rejects_a_missing_project(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")

    with pytest.raises(ProjectNotFoundError):
        repository.is_project_dirty("missing")


def test_missing_objects_have_specific_errors(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")

    with pytest.raises(ProjectNotFoundError):
        repository.get("missing")
    with pytest.raises(EntryNotFoundError):
        repository.get_entry("missing", "entry-1")


def test_get_entries_preserves_requested_order_and_duplicates(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    project.add_entry(TranslationEntry("entry-2", ("dialog", 1), "Bye"))
    repository.create(project)

    entries = repository.get_entries(
        project.id, ("entry-2", "entry-1", "entry-2")
    )

    assert [entry.id for entry in entries] == ["entry-2", "entry-1", "entry-2"]


def test_get_entries_reports_all_missing_ids(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = make_project()
    repository.create(project)

    with pytest.raises(EntryNotFoundError, match="missing-1.*missing-2"):
        repository.get_entries(project.id, ("missing-1", "entry-1", "missing-2"))


def test_document_lookup_uses_composite_index(tmp_path: Path) -> None:
    database_path = tmp_path / "project.db"
    repository = SQLiteProjectRepository(database_path)
    project = make_project()
    repository.create(project)

    with sqlite3.connect(database_path) as connection:
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM entries "
            "WHERE project_id = ? AND document_id = ?",
            (project.id, project.documents[0].id),
        ).fetchall()
        operation_indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(translation_operation_entries)"
            ).fetchall()
        }

    assert any("entries_document_lookup" in str(row[3]) for row in plan)
    assert "translation_operation_entries_entry_lookup" in operation_indexes


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

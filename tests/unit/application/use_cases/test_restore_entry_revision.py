from __future__ import annotations

from pathlib import Path

import pytest

from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.restore_entry_revision import RestoreEntryRevision
from locaforge.application.use_cases.set_entry_locked import SetEntryLocked
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project
from locaforge.infrastructure.persistence.sqlite_project_repository import (
    SQLiteProjectRepository,
)


def make_repository(tmp_path: Path) -> SQLiteProjectRepository:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    repository.create(
        Project(
            id="project-1",
            name="Dialog",
            source_language="en",
            target_language="ru",
            source_document={"text": "Hello"},
            entries=[TranslationEntry("entry-1", ("text",), "Hello")],
        )
    )
    return repository


def test_restore_revision_reapplies_previous_translation(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    editor = EditTranslation(repository)
    editor.execute("project-1", "entry-1", "Привет")
    editor.execute("project-1", "entry-1", "Здравствуйте")
    revision = repository.list_entry_revisions("project-1", "entry-1")[0]

    restored = RestoreEntryRevision(repository).execute(
        "project-1", "entry-1", revision.revision_id
    )

    assert restored.translation == "Привет"
    assert repository.list_entry_revisions("project-1", "entry-1")[0].translation == (
        "Здравствуйте"
    )


def test_locked_entry_revision_cannot_be_restored(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    EditTranslation(repository).execute("project-1", "entry-1", "Привет")
    revision = repository.list_entry_revisions("project-1", "entry-1")[0]
    SetEntryLocked(repository).execute("project-1", "entry-1", True)

    with pytest.raises(ValueError, match="Unlock"):
        RestoreEntryRevision(repository).execute(
            "project-1", "entry-1", revision.revision_id
        )

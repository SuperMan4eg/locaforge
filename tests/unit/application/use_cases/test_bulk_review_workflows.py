from __future__ import annotations

from pathlib import Path

import pytest

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.use_cases.set_entries_approval import SetEntriesApproval
from locaforge.application.use_cases.set_entries_locked import SetEntriesLocked
from locaforge.domain.entry import EntryStatus, TranslationEntry
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
            source_document={"one": "First", "two": "Second", "three": "Third"},
            entries=[
                TranslationEntry(
                    "entry-1",
                    ("one",),
                    "First",
                    translation="Первый",
                    status=EntryStatus.NEEDS_REVIEW,
                ),
                TranslationEntry(
                    "entry-2",
                    ("two",),
                    "Second",
                    translation="Второй",
                    status=EntryStatus.NEEDS_REVIEW,
                ),
                TranslationEntry("entry-3", ("three",), "Third"),
            ],
        )
    )
    return repository


def test_batch_approval_and_reopen_update_selected_entries(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    workflow = SetEntriesApproval(repository)

    assert workflow.execute("project-1", ("entry-1", "entry-2"), True) == (
        "entry-1",
        "entry-2",
    )
    assert all(
        repository.get_entry("project-1", entry_id).status is EntryStatus.APPROVED
        for entry_id in ("entry-1", "entry-2")
    )

    assert workflow.execute("project-1", ("entry-2",), False) == ("entry-2",)
    assert repository.get_entry("project-1", "entry-2").status is EntryStatus.NEEDS_REVIEW


def test_batch_approval_rejects_entire_selection_before_mutating(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.replace_validation_issues(
        "project-1",
        "entry-2",
        (ValidationIssue(ValidationCode.GLOSSARY_MISMATCH, "Wrong term"),),
    )

    with pytest.raises(ValueError, match="cannot be approved"):
        SetEntriesApproval(repository).execute(
            "project-1", ("entry-1", "entry-2"), True
        )

    assert repository.get_entry("project-1", "entry-1").status is EntryStatus.NEEDS_REVIEW


def test_batch_lock_rejects_untranslated_entries_before_mutating(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)

    with pytest.raises(ValueError, match="cannot be locked"):
        SetEntriesLocked(repository).execute(
            "project-1", ("entry-1", "entry-3"), True
        )

    assert repository.get_entry("project-1", "entry-1").locked is False


def test_batch_lock_and_unlock_update_selected_entries(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    workflow = SetEntriesLocked(repository)

    assert workflow.execute("project-1", ("entry-1", "entry-2"), True) == (
        "entry-1",
        "entry-2",
    )
    assert workflow.execute("project-1", ("entry-1", "entry-2"), False) == (
        "entry-1",
        "entry-2",
    )

from __future__ import annotations

from pathlib import Path

import pytest

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.use_cases.set_entry_approval import SetEntryApproval
from locaforge.application.use_cases.set_entry_locked import SetEntryLocked
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
            source_document={"text": "Hello"},
            entries=[
                TranslationEntry(
                    "entry-1",
                    ("text",),
                    "Hello",
                    translation="Привет",
                    status=EntryStatus.NEEDS_REVIEW,
                )
            ],
        )
    )
    return repository


def test_entry_can_be_approved_and_reopened(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    workflow = SetEntryApproval(repository)

    workflow.execute("project-1", "entry-1", True)
    assert repository.get_entry("project-1", "entry-1").status is EntryStatus.APPROVED

    workflow.execute("project-1", "entry-1", False)
    assert repository.get_entry("project-1", "entry-1").status is EntryStatus.NEEDS_REVIEW


def test_entry_with_validation_issue_cannot_be_approved(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.replace_validation_issues(
        "project-1",
        "entry-1",
        (ValidationIssue(ValidationCode.GLOSSARY_MISMATCH, "Wrong term"),),
    )

    with pytest.raises(ValueError, match="validation issues"):
        SetEntryApproval(repository).execute("project-1", "entry-1", True)


def test_entry_can_be_locked_and_unlocked(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    workflow = SetEntryLocked(repository)

    workflow.execute("project-1", "entry-1", True)
    assert repository.get_entry("project-1", "entry-1").locked is True

    workflow.execute("project-1", "entry-1", False)
    assert repository.get_entry("project-1", "entry-1").locked is False

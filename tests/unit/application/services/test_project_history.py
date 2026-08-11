from collections.abc import Mapping, Sequence
from typing import cast

import pytest

from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ValidationCode,
    ValidationIssue,
)
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.services.project_history import ProjectHistoryService
from locaforge.domain.entry import TranslationEntry


class FakeHistoryRepository:
    def __init__(self) -> None:
        self.entries = {
            "entry-1": TranslationEntry("entry-1", ("first",), "First"),
            "entry-2": TranslationEntry("entry-2", ("second",), "Second"),
        }
        self.issues = (
            EntryValidationIssue(
                "entry-1", ValidationCode.EMPTY_TRANSLATION, "Empty"
            ),
        )
        self.recorded_entries: tuple[TranslationEntry, ...] = ()
        self.recorded_issues: Mapping[str, Sequence[ValidationIssue]] = {}
        self.recorded_label = ""
        self.undo_result: tuple[TranslationEntry, ...] = ()
        self.redo_result: tuple[TranslationEntry, ...] = ()

    def get_entry(self, project_id: str, entry_id: str) -> TranslationEntry:
        assert project_id == "project-1"
        return self.entries[entry_id]

    def list_validation_issues(
        self, project_id: str
    ) -> tuple[EntryValidationIssue, ...]:
        assert project_id == "project-1"
        return self.issues

    def record_translation_operation(
        self,
        project_id: str,
        previous_entries: Sequence[TranslationEntry],
        previous_issues: Mapping[str, Sequence[ValidationIssue]],
        label: str,
    ) -> None:
        assert project_id == "project-1"
        self.recorded_entries = tuple(previous_entries)
        self.recorded_issues = previous_issues
        self.recorded_label = label

    def undo_last_translation_operation(
        self, project_id: str
    ) -> tuple[TranslationEntry, ...]:
        assert project_id == "project-1"
        return self.undo_result

    def redo_last_translation_operation(
        self, project_id: str
    ) -> tuple[TranslationEntry, ...]:
        assert project_id == "project-1"
        return self.redo_result


def as_repository(repository: FakeHistoryRepository) -> ProjectRepository:
    return cast(ProjectRepository, repository)


def test_snapshot_deduplicates_entries_and_includes_empty_issue_groups() -> None:
    repository = FakeHistoryRepository()

    entries, issues = ProjectHistoryService().snapshot(
        as_repository(repository),
        "project-1",
        ("entry-1", "entry-1", "entry-2"),
    )

    assert [entry.id for entry in entries] == ["entry-1", "entry-2"]
    assert issues == {
        "entry-1": (ValidationIssue(ValidationCode.EMPTY_TRANSLATION, "Empty"),),
        "entry-2": (),
    }


def test_record_updated_entries_excludes_entries_not_changed_by_operation() -> None:
    repository = FakeHistoryRepository()
    previous_entries = tuple(repository.entries.values())
    previous_issues = {"entry-1": (), "entry-2": ()}

    ProjectHistoryService().record_updated_entries(
        as_repository(repository),
        "project-1",
        ("entry-2",),
        previous_entries,
        previous_issues,
        "Lock translations",
    )

    assert [entry.id for entry in repository.recorded_entries] == ["entry-2"]
    assert repository.recorded_issues is previous_issues
    assert repository.recorded_label == "Lock translations"


def test_undo_and_redo_reject_empty_repository_results() -> None:
    repository = as_repository(FakeHistoryRepository())
    service = ProjectHistoryService()

    with pytest.raises(ValueError, match="no translation operation to undo"):
        service.undo(repository, "project-1")
    with pytest.raises(ValueError, match="no translation operation to redo"):
        service.redo(repository, "project-1")


def test_undo_returns_restored_entries() -> None:
    fake = FakeHistoryRepository()
    fake.undo_result = (fake.entries["entry-1"],)

    restored = ProjectHistoryService().undo(as_repository(fake), "project-1")

    assert restored == fake.undo_result

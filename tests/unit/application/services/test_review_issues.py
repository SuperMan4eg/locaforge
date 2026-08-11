from collections.abc import Mapping, Sequence

from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ValidationCode,
    ValidationIssue,
)
from locaforge.application.services.review_issues import ReviewIssueService
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project


class Repository:
    def __init__(self, issues: tuple[EntryValidationIssue, ...]) -> None:
        self.entry = TranslationEntry("entry-1", ("text",), "Hello")
        self.issues = issues
        self.operations: list[tuple[object, ...]] = []
        self.dirty: list[str] = []

    def get_entry(self, _project_id: str, _entry_id: str) -> TranslationEntry:
        return self.entry

    def list_validation_issues(
        self, _project_id: str
    ) -> tuple[EntryValidationIssue, ...]:
        return self.issues

    def replace_validation_issues(
        self,
        _project_id: str,
        _entry_id: str,
        issues: Sequence[ValidationIssue],
    ) -> None:
        self.issues = tuple(
            EntryValidationIssue("entry-1", issue.code, issue.message)
            for issue in issues
        )

    def mark_project_dirty(self, project_id: str) -> None:
        self.dirty.append(project_id)

    def record_translation_operation(
        self,
        project_id: str,
        entries: Sequence[TranslationEntry],
        issues: Mapping[str, Sequence[ValidationIssue]],
        label: str,
    ) -> None:
        self.operations.append((project_id, tuple(entries), issues, label))


def test_dismisses_ai_issue_and_records_undo_operation() -> None:
    repository = Repository(
        (
            EntryValidationIssue("entry-1", ValidationCode.AI_REVIEW, "Wording"),
            EntryValidationIssue(
                "entry-1", ValidationCode.PLACEHOLDER_MISMATCH, "Placeholder"
            ),
        )
    )

    ReviewIssueService().dismiss_one(  # type: ignore[arg-type]
        repository, Project("p", "Demo", "en", "ru"), "entry-1"
    )

    assert [issue.code for issue in repository.issues] == [
        ValidationCode.PLACEHOLDER_MISMATCH
    ]
    assert repository.operations[0][3] == "Dismiss AI review issue"
    assert repository.dirty == ["p"]


def test_no_ai_issue_does_not_create_undo_operation() -> None:
    repository = Repository(())

    ReviewIssueService().dismiss_one(  # type: ignore[arg-type]
        repository, Project("p", "Demo", "en", "ru"), "entry-1"
    )

    assert repository.operations == []
    assert repository.dirty == ["p"]

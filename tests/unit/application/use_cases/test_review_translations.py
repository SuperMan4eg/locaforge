from pathlib import Path

from locaforge.application.dto.review import ReviewResponse, ReviewResult
from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.use_cases.dismiss_ai_review_issue import DismissAiReviewIssue
from locaforge.application.use_cases.dismiss_ai_review_issues import DismissAiReviewIssues
from locaforge.application.use_cases.review_translations import ReviewTranslations
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project
from locaforge.infrastructure.persistence.sqlite_project_repository import SQLiteProjectRepository


class StubReviewer:
    def review(self, request):
        return ReviewResponse((ReviewResult(request.entries[0].entry_id, "Wrong meaning"),))


def test_ai_review_stores_issue_without_changing_translation(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    repository.create(
        Project(
            "project-1",
            "Dialog",
            "zh",
            "en",
            [
                TranslationEntry(
                    "entry-1",
                    ("text",),
                    "保存",
                    "Preserve",
                    EntryStatus.NEEDS_REVIEW,
                )
            ],
            {},
        )
    )

    issue_count = ReviewTranslations(repository, StubReviewer()).execute(
        "project-1", ("entry-1",), "qwen3", 5.0
    )

    assert issue_count == 1
    assert repository.get_entry("project-1", "entry-1").translation == "Preserve"
    assert repository.list_validation_issues("project-1")[0].code is ValidationCode.AI_REVIEW


def test_dismiss_ai_issue_preserves_structural_validation(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    repository.create(
        Project(
            "project-1",
            "Dialog",
            "en",
            "ru",
            [TranslationEntry("entry-1", ("text",), "Hello", "Привет")],
            {},
        )
    )
    repository.replace_validation_issues(
        "project-1",
        "entry-1",
        (
            ValidationIssue(ValidationCode.AI_REVIEW, "Wrong meaning"),
            ValidationIssue(ValidationCode.PLACEHOLDER_MISMATCH, "Missing placeholder"),
        ),
    )

    DismissAiReviewIssue(repository).execute("project-1", "entry-1")

    issues = repository.list_validation_issues("project-1")
    assert [issue.code for issue in issues] == [ValidationCode.PLACEHOLDER_MISMATCH]
    assert repository.get("project-1").dirty is True


def test_dismisses_ai_issues_for_multiple_entries(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    repository.create(
        Project(
            "project-1",
            "Dialog",
            "en",
            "ru",
            [
                TranslationEntry("one", ("one",), "One", "Один"),
                TranslationEntry("two", ("two",), "Two", "Два"),
            ],
            {},
        )
    )
    repository.replace_validation_issues_bulk(
        "project-1",
        {
            "one": (ValidationIssue(ValidationCode.AI_REVIEW, "Check meaning"),),
            "two": (
                ValidationIssue(ValidationCode.AI_REVIEW, "Check wording"),
                ValidationIssue(ValidationCode.PLACEHOLDER_MISMATCH, "Missing token"),
            ),
        },
    )

    dismissed_count = DismissAiReviewIssues(repository).execute(
        "project-1", ("one", "two")
    )

    assert dismissed_count == 2
    issues = repository.list_validation_issues("project-1")
    assert [(issue.entry_id, issue.code) for issue in issues] == [
        ("two", ValidationCode.PLACEHOLDER_MISMATCH)
    ]

from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ValidationCode,
)
from locaforge.application.services.project_validation import ProjectValidationService
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project


class Repository:
    def __init__(self, issues: tuple[EntryValidationIssue, ...]) -> None:
        self.issues = issues

    def list_validation_issues(
        self, _project_id: str
    ) -> tuple[EntryValidationIssue, ...]:
        return self.issues


def make_project() -> Project:
    untranslated = TranslationEntry("untranslated", ("one",), "One")
    translated = TranslationEntry("translated", ("two",), "Two")
    translated.set_translation("Два")
    approved = TranslationEntry("approved", ("three",), "Three")
    approved.set_translation("Три")
    approved.approve()
    locked = TranslationEntry("locked", ("four",), "Four")
    locked.set_translation("Четыре")
    locked.set_locked(True)
    error = TranslationEntry(
        "error", ("five",), "Five", translation="Пять", status=EntryStatus.ERROR
    )
    return Project(
        "p",
        "Demo",
        "en",
        "ru",
        entries=[untranslated, translated, approved, locked, error],
    )


def test_selects_only_unlocked_untranslated_entries() -> None:
    assert ProjectValidationService.untranslated_entry_ids(make_project()) == (
        "untranslated",
    )


def test_selects_only_unlocked_needs_review_translations() -> None:
    assert ProjectValidationService.reviewable_entry_ids(make_project()) == (
        "translated",
    )


def test_lists_persisted_validation_issues() -> None:
    issue = EntryValidationIssue(
        "error", ValidationCode.PLACEHOLDER_MISMATCH, "Placeholder"
    )

    assert ProjectValidationService.issues(  # type: ignore[arg-type]
        Repository((issue,)), make_project()
    ) == (issue,)

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.use_cases.validate_project import ValidateProject
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.project import Project
from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary
from locaforge.infrastructure.persistence.sqlite_project_repository import (
    SQLiteProjectRepository,
)


class CountingSQLiteGlossary(SQLiteGlossary):
    def __init__(self, database_path: Path) -> None:
        self.batch_calls = 0
        super().__init__(database_path)

    def find_for_sources_batch(
        self,
        source_language: str,
        target_language: str,
        sources: Sequence[str],
    ) -> tuple[tuple[GlossaryTerm, ...], ...]:
        self.batch_calls += 1
        return super().find_for_sources_batch(
            source_language, target_language, sources
        )


def make_repository(tmp_path: Path) -> SQLiteProjectRepository:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    repository.create(
        Project(
            id="project-1",
            name="Dialog",
            source_language="en",
            target_language="ru",
            source_document={"save": "Save game", "hello": "Hello"},
            entries=[
                TranslationEntry(
                    "entry-1",
                    ("save",),
                    "Save game",
                    translation="Записать игру",
                    status=EntryStatus.TRANSLATED,
                ),
                TranslationEntry(
                    "entry-2",
                    ("hello",),
                    "Hello",
                    translation="Привет",
                    status=EntryStatus.ERROR,
                ),
                TranslationEntry("entry-3", ("empty",), "Untranslated"),
            ],
        )
    )
    return repository


def test_validate_project_rechecks_glossary_and_restores_valid_error_entry(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    glossary.store(GlossaryTerm("en", "ru", "Save", "Сохранить"))

    result = ValidateProject(repository, glossary=glossary).execute("project-1")

    assert result.entries_checked == 2
    assert result.entries_with_issues == 1
    assert repository.get_entry("project-1", "entry-1").status is EntryStatus.ERROR
    assert repository.get_entry("project-1", "entry-2").status is EntryStatus.NEEDS_REVIEW
    assert repository.list_validation_issues("project-1")[0].code is (
        ValidationCode.GLOSSARY_MISMATCH
    )


def test_validate_project_matches_glossary_in_one_batch(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    glossary = CountingSQLiteGlossary(tmp_path / "glossary.db")
    glossary.store(GlossaryTerm("en", "ru", "Save", "Сохранить"))

    ValidateProject(repository, glossary=glossary).execute("project-1")

    assert glossary.batch_calls == 1


def test_validate_project_leaves_untranslated_model_errors_untouched(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.replace_validation_issues(
        "project-1",
        "entry-3",
        (ValidationIssue(ValidationCode.MODEL_RESPONSE, "Backend failed"),),
    )

    ValidateProject(repository).execute("project-1")

    issues = repository.list_validation_issues("project-1")
    assert any(issue.entry_id == "entry-3" for issue in issues)


def test_validate_project_reports_consistency_without_marking_entries_as_errors(
    tmp_path: Path,
) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    repository.create(
        Project(
            id="project-1",
            name="Dialog",
            source_language="en",
            target_language="ru",
            source_document={"one": "Save", "two": "Save"},
            entries=[
                TranslationEntry(
                    "one",
                    ("one",),
                    "Save",
                    translation="Сохранить",
                    status=EntryStatus.NEEDS_REVIEW,
                ),
                TranslationEntry(
                    "two",
                    ("two",),
                    "Save",
                    translation="Записать",
                    status=EntryStatus.NEEDS_REVIEW,
                ),
            ],
        )
    )

    result = ValidateProject(repository).execute("project-1")

    assert result.entries_with_issues == 2
    assert repository.get_entry("project-1", "one").status is EntryStatus.NEEDS_REVIEW
    issues = repository.list_validation_issues("project-1")
    assert {issue.code for issue in issues} == {ValidationCode.INCONSISTENT_TRANSLATION}


def test_validate_project_preserves_ai_review_issue(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.replace_validation_issues(
        "project-1",
        "entry-2",
        (ValidationIssue(ValidationCode.AI_REVIEW, "Check meaning"),),
    )

    ValidateProject(repository).execute("project-1")

    issues = repository.list_validation_issues("project-1")
    assert any(
        issue.entry_id == "entry-2" and issue.code is ValidationCode.AI_REVIEW
        for issue in issues
    )

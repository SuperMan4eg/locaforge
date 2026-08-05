from pathlib import Path

from locaforge.application.use_cases.apply_translation_to_matches import (
    ApplyTranslationToMatches,
)
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
                TranslationEntry(
                    "locked",
                    ("locked",),
                    "Save",
                    translation="Зафиксировано",
                    status=EntryStatus.APPROVED,
                    locked=True,
                ),
                TranslationEntry(
                    "context",
                    ("context",),
                    "Save",
                    translation="Сохранить файл",
                    context="file",
                    status=EntryStatus.NEEDS_REVIEW,
                ),
            ],
        )
    )
    return repository


def test_applies_translation_to_matching_unlocked_entries(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    use_case = ApplyTranslationToMatches(repository)

    updated_entry_ids = use_case.execute("project-1", "one", "Сохранить")

    assert updated_entry_ids == ("one", "two")
    assert repository.get_entry("project-1", "two").translation == "Сохранить"
    assert repository.get_entry("project-1", "locked").translation == "Зафиксировано"
    assert repository.get_entry("project-1", "context").translation == "Сохранить файл"


def test_lists_matching_entries_without_locked_or_other_context_entries(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)

    entry_ids = ApplyTranslationToMatches(repository).matching_entry_ids(
        "project-1", "one"
    )

    assert entry_ids == ("one", "two")

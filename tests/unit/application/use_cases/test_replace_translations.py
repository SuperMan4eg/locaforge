from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.replace_translations import ReplaceTranslations
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project
from locaforge.infrastructure.persistence.sqlite_project_repository import (
    SQLiteProjectRepository,
)


def test_replace_updates_matching_editable_translations_and_keeps_history(tmp_path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = Project(
        id="project-1",
        name="Project",
        source_language="en",
        target_language="ru",
        entries=[
            TranslationEntry("entry-1", ("first",), "First"),
            TranslationEntry("entry-2", ("second",), "Second"),
            TranslationEntry(
                "entry-3",
                ("third",),
                "Third",
                translation="Old locked",
                status=EntryStatus.TRANSLATED,
                locked=True,
            ),
        ],
        source_document={},
    )
    repository.create(project)
    EditTranslation(repository).execute("project-1", "entry-1", "Old value")
    EditTranslation(repository).execute("project-1", "entry-2", "No match")

    updated = ReplaceTranslations(repository).execute("project-1", "Old", "New")

    assert updated == ("entry-1",)
    assert repository.get_entry("project-1", "entry-1").translation == "New value"
    assert repository.get_entry("project-1", "entry-1").status is EntryStatus.NEEDS_REVIEW
    assert repository.get_entry("project-1", "entry-3").translation == "Old locked"
    revisions = repository.list_entry_revisions("project-1", "entry-1")
    assert [revision.translation for revision in revisions] == [
        "Old value",
        None,
    ]


def test_replace_rejects_empty_search_text(tmp_path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")

    try:
        ReplaceTranslations(repository).execute("project-1", "", "replacement")
    except ValueError as error:
        assert str(error) == "Text to find must not be empty"
    else:
        raise AssertionError("Expected replacement without search text to fail")

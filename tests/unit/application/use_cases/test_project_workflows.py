from pathlib import Path

from locaforge.application.dto.validation import ValidationCode
from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.save_project import SaveProject
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.project import Project
from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary
from locaforge.infrastructure.persistence.sqlite_project_repository import SQLiteProjectRepository
from locaforge.infrastructure.persistence.sqlite_translation_memory import (
    SQLiteTranslationMemory,
)


def test_edit_then_save_updates_translation_and_clears_dirty_flag(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = Project(
        id="project-1",
        name="Dialog",
        source_language="en",
        target_language="ru",
        source_document={"text": "Hello"},
        entries=[TranslationEntry("entry-1", ("text",), "Hello")],
    )
    repository.create(project)

    EditTranslation(repository).execute(project.id, "entry-1", "Привет")
    assert repository.get(project.id).dirty is True

    SaveProject(repository).execute(project.id)

    restored = repository.get(project.id)
    assert restored.entries[0].translation == "Привет"
    assert restored.dirty is False


def test_manual_edit_persists_and_clears_validation_issues(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = Project(
        id="project-1",
        name="Dialog",
        source_language="en",
        target_language="ru",
        source_document={"text": "Hello {name}"},
        entries=[
            TranslationEntry(
                "entry-1", ("text",), "Hello {name}", max_length=20
            )
        ],
    )
    repository.create(project)

    EditTranslation(repository).execute(project.id, "entry-1", "Очень длинный перевод")

    assert repository.get_entry(project.id, "entry-1").status is EntryStatus.ERROR
    assert len(repository.list_validation_issues(project.id)) == 2

    EditTranslation(repository).execute(project.id, "entry-1", "Привет {name}")
    assert repository.get_entry(project.id, "entry-1").status is EntryStatus.NEEDS_REVIEW
    assert not repository.list_validation_issues(project.id)


def test_invalid_manual_edit_is_not_added_to_translation_memory(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    project = Project(
        id="project-1",
        name="Dialog",
        source_language="en",
        target_language="ru",
        source_document={"text": "Hello {name}"},
        entries=[TranslationEntry("entry-1", ("text",), "Hello {name}")],
    )
    repository.create(project)

    EditTranslation(repository, translation_memory=memory).execute(
        project.id, "entry-1", "Привет"
    )

    assert memory.find_exact("en", "ru", "Hello {name}") is None


def test_manual_edit_that_violates_glossary_is_marked_as_error(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    glossary.store(GlossaryTerm("en", "ru", "Save", "Сохранить"))
    project = Project(
        id="project-1",
        name="Dialog",
        source_language="en",
        target_language="ru",
        source_document={"text": "Save game"},
        entries=[TranslationEntry("entry-1", ("text",), "Save game")],
    )
    repository.create(project)

    EditTranslation(repository, glossary=glossary).execute(
        project.id, "entry-1", "Записать игру"
    )

    assert repository.get_entry(project.id, "entry-1").status is EntryStatus.ERROR
    assert repository.list_validation_issues(project.id)[0].code is (
        ValidationCode.GLOSSARY_MISMATCH
    )

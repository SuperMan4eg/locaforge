import pytest

from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project


def test_add_entry_marks_project_dirty() -> None:
    project = Project("project-1", "Dialog", "en", "ru")
    entry = TranslationEntry("entry-1", ("dialog", "greeting"), "Hello")

    project.add_entry(entry)

    assert project.dirty is True
    assert project.get_entry("entry-1") is entry


def test_duplicate_entry_id_is_rejected() -> None:
    project = Project("project-1", "Dialog", "en", "ru")
    project.add_entry(TranslationEntry("entry-1", ("first",), "Hello"))

    with pytest.raises(ValueError, match="already exists"):
        project.add_entry(TranslationEntry("entry-1", ("second",), "Goodbye"))


def test_duplicate_entry_ids_are_rejected_during_project_creation() -> None:
    with pytest.raises(ValueError, match="Duplicate project entry id"):
        Project(
            "project-1",
            "Dialog",
            "en",
            "ru",
            entries=[
                TranslationEntry("entry-1", ("first",), "Hello"),
                TranslationEntry("entry-1", ("second",), "Goodbye"),
            ],
        )


def test_entry_index_recovers_after_direct_list_mutations() -> None:
    first = TranslationEntry("entry-1", ("first",), "Hello")
    project = Project("project-1", "Dialog", "en", "ru", entries=[first])
    replacement = TranslationEntry("entry-2", ("second",), "Goodbye")

    project.entries[0] = replacement

    assert project.get_entry("entry-2") is replacement
    with pytest.raises(KeyError, match="entry-1"):
        project.get_entry("entry-1")


def test_entry_index_recovers_after_direct_append() -> None:
    project = Project("project-1", "Dialog", "en", "ru")
    appended = TranslationEntry("entry-1", ("first",), "Hello")

    project.entries.append(appended)

    assert project.get_entry("entry-1") is appended


def test_entry_index_recovers_after_direct_removal() -> None:
    removed = TranslationEntry("entry-1", ("first",), "Hello")
    remaining = TranslationEntry("entry-2", ("second",), "Goodbye")
    project = Project(
        "project-1",
        "Dialog",
        "en",
        "ru",
        entries=[removed, remaining],
    )

    project.entries.remove(removed)

    assert project.get_entry("entry-2") is remaining
    with pytest.raises(KeyError, match="entry-1"):
        project.get_entry("entry-1")


def test_legacy_project_creates_a_default_document_and_assigns_entries() -> None:
    entry = TranslationEntry("entry-1", ("hello",), "Hello")
    project = Project(
        "project-1",
        "Dialog",
        "en",
        "ru",
        entries=[entry],
        source_document={"hello": "Hello"},
    )

    assert len(project.documents) == 1
    assert project.documents[0].source_format == "legacy"
    assert project.documents[0].source_document == {"hello": "Hello"}
    assert entry.document_id == project.documents[0].id


def test_translation_candidates_are_kept_separate_until_selected() -> None:
    entry = TranslationEntry("entry-1", ("hello",), "Hello")
    entry.mark_model_translation("Привет")
    entry.set_reviewer_translation("Здравствуйте")

    assert entry.translation == "Привет"
    assert entry.model_translation == "Привет"
    assert entry.reviewer_translation == "Здравствуйте"

    entry.select_translation_candidate("reviewer")

    assert entry.translation == "Здравствуйте"
    assert entry.status is EntryStatus.NEEDS_REVIEW

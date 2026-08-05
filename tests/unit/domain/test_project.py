import pytest

from locaforge.domain.entry import TranslationEntry
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

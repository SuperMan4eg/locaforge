from collections.abc import Sequence

import pytest

from locaforge.application.services.translation_editing import TranslationEditingService
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project


class Repository:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.operations: list[tuple[object, ...]] = []

    def get(self, _project_id: str) -> Project:
        return self.project

    def get_entry(self, _project_id: str, entry_id: str) -> TranslationEntry:
        return self.project.get_entry(entry_id)

    def get_entries(
        self, _project_id: str, entry_ids: Sequence[str]
    ) -> tuple[TranslationEntry, ...]:
        return tuple(self.project.get_entry(entry_id) for entry_id in entry_ids)

    def list_validation_issues(self, _project_id: str) -> tuple[()]:
        return ()

    def update_entry(self, _project_id: str, _entry: TranslationEntry) -> None:
        pass

    def replace_validation_issues(self, *_args: object) -> None:
        pass

    def record_translation_operation(self, *args: object) -> None:
        self.operations.append(args)


def make_project() -> Project:
    entry = TranslationEntry(
        "entry-1",
        ("text",),
        "Hello",
        model_translation="Модель",
        reviewer_translation="Редактор",
    )
    return Project("p", "Demo", "en", "ru", entries=[entry])


def test_selects_reviewer_candidate_as_undoable_manual_edit() -> None:
    project = make_project()
    repository = Repository(project)
    service = TranslationEditingService(None, None)

    entry = service.select_candidate(  # type: ignore[arg-type]
        repository, project, "entry-1", "reviewer"
    )

    assert entry.translation == "Редактор"
    assert repository.operations[0][0] == project.id
    assert repository.operations[0][3] == "Edit translation"


def test_rejects_unknown_or_missing_candidate_before_edit() -> None:
    project = make_project()
    project.entries[0].reviewer_translation = None
    service = TranslationEditingService(None, None)

    with pytest.raises(ValueError, match="Unknown translation candidate"):
        service.select_candidate(object(), project, "entry-1", "other")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="No reviewer translation"):
        service.select_candidate(object(), project, "entry-1", "reviewer")  # type: ignore[arg-type]

import json
from pathlib import Path

from locaforge.application.use_cases.create_project_from_json import CreateProjectFromJson
from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.export_project_json import ExportProjectJson
from locaforge.application.use_cases.open_project_file import OpenProjectFile
from locaforge.application.use_cases.save_project_file import SaveProjectFile
from locaforge.infrastructure.formats.json_format import JsonFileExporter, JsonFileImporter
from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
from locaforge.infrastructure.persistence.sqlite_project_repository_factory import (
    SQLiteProjectRepositoryFactory,
)


def test_open_edit_save_reopen_and_export_project(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        json.dumps({"dialog": {"greeting": "Hello", "count": 1}}), encoding="utf-8"
    )
    project_path = tmp_path / "dialog.lfproj"
    repository_factory = SQLiteProjectRepositoryFactory()
    CreateProjectFromJson(
        JsonFileImporter(),
        LfprojContainer(tmp_path / "create-work"),
        repository_factory,
    ).execute(source_path, project_path, "en", "ru")

    open_container = LfprojContainer(tmp_path / "open-work")
    opened = OpenProjectFile(open_container, repository_factory).execute(project_path)
    repository = repository_factory.create(opened.session.database_path)
    entry_id = opened.project.entries[0].id
    EditTranslation(repository).execute(opened.project.id, entry_id, "Привет")

    saved_project = SaveProjectFile(open_container, repository_factory).execute(opened.session)

    assert saved_project.dirty is False
    assert project_path.with_suffix(".lfproj.bak").is_file()

    reopened = OpenProjectFile(
        LfprojContainer(tmp_path / "reopen-work"), repository_factory
    ).execute(project_path)
    assert reopened.project.entries[0].translation == "Привет"
    assert reopened.project.dirty is False

    destination = tmp_path / "dialog_ru.json"
    ExportProjectJson(JsonFileExporter(), repository_factory).execute(
        reopened.session, destination
    )
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "dialog": {"greeting": "Привет", "count": 1}
    }

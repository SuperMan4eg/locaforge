import json
import sqlite3
import zipfile
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


def test_open_migrate_save_and_reopen_legacy_project_container(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, source_language TEXT NOT NULL,
                target_language TEXT NOT NULL, source_document TEXT NOT NULL,
                model_settings TEXT NOT NULL DEFAULT '{}', dirty INTEGER NOT NULL
            );
            CREATE TABLE entries (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, row_order INTEGER NOT NULL,
                key_path TEXT NOT NULL, source TEXT NOT NULL, entry_key TEXT,
                translation TEXT, status TEXT NOT NULL, locked INTEGER NOT NULL,
                context TEXT, max_length INTEGER, placeholders TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("old", "Legacy", "en", "ru", '{"hello": "Hello"}', "{}", 0),
        )
        connection.execute(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "entry-1",
                "old",
                0,
                '["hello"]',
                "Hello",
                "hello",
                "Привет",
                "needs_review",
                0,
                None,
                None,
                "[]",
            ),
        )
    legacy_path = tmp_path / "legacy.lfproj"
    with zipfile.ZipFile(legacy_path, "w") as archive:
        archive.write(database_path, "project.db")
        archive.writestr(
            "metadata.json",
            json.dumps(
                {
                    "format_version": 1,
                    "project_id": "old",
                    "source_file": "legacy.json",
                    "source_format": "json",
                }
            ),
        )
    repository_factory = SQLiteProjectRepositoryFactory()
    container = LfprojContainer(tmp_path / "opened")

    opened = OpenProjectFile(container, repository_factory).execute(legacy_path)
    SaveProjectFile(container, repository_factory).execute(opened.session)
    reopened = OpenProjectFile(
        LfprojContainer(tmp_path / "reopened"), repository_factory
    ).execute(legacy_path)
    export_path = tmp_path / "legacy-export.json"
    ExportProjectJson(JsonFileExporter(), repository_factory).execute(
        reopened.session, export_path
    )

    assert reopened.session.metadata["format_version"] == 2
    assert reopened.project.model_settings_override_enabled is True
    assert reopened.project.documents[0].source_format == "json"
    assert reopened.project.entries[0].translation == "Привет"
    assert json.loads(export_path.read_text(encoding="utf-8")) == {"hello": "Привет"}

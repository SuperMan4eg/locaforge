import json
from pathlib import Path

import pytest

from locaforge.application.use_cases.create_project_from_json import CreateProjectFromJson
from locaforge.infrastructure.formats.json_format import JsonFileImporter
from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
from locaforge.infrastructure.persistence.sqlite_project_repository import SQLiteProjectRepository
from locaforge.infrastructure.persistence.sqlite_project_repository_factory import (
    SQLiteProjectRepositoryFactory,
)


def test_creates_portable_project_from_json_without_modifying_source(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_document = {"dialog": [{"speaker": "Guide", "text": "Hello"}], "version": 1}
    source_path.write_text(json.dumps(source_document), encoding="utf-8")
    source_bytes = source_path.read_bytes()
    destination = tmp_path / "dialog.lfproj"
    container = LfprojContainer(tmp_path / "working")
    use_case = CreateProjectFromJson(
        JsonFileImporter(), container, SQLiteProjectRepositoryFactory()
    )

    created = use_case.execute(source_path, destination, "en", "ru")

    assert destination.is_file()
    assert source_path.read_bytes() == source_bytes
    assert created.session.container_path == destination
    assert len(created.project.entries) == 2

    opened = LfprojContainer(tmp_path / "reopened").open(destination)
    restored = SQLiteProjectRepository(opened.database_path).get(created.project.id)
    assert restored == created.project
    assert opened.metadata["source_file"] == "dialog.json"
    assert opened.metadata["source_language"] == "en"
    assert opened.metadata["target_language"] == "ru"


def test_rejects_destination_without_lfproj_extension(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    use_case = CreateProjectFromJson(
        JsonFileImporter(),
        LfprojContainer(tmp_path / "working"),
        SQLiteProjectRepositoryFactory(),
    )

    with pytest.raises(ValueError, match=".lfproj"):
        use_case.execute(source_path, tmp_path / "dialog.zip", "en", "ru")

import zipfile
from pathlib import Path

import pytest

from locaforge.application.project_session import ProjectSession
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project
from locaforge.infrastructure.persistence.lfproj_container import (
    LfprojContainer,
    ProjectContainerError,
)
from locaforge.infrastructure.persistence.sqlite_project_repository import SQLiteProjectRepository


def create_project_session(tmp_path: Path) -> tuple[LfprojContainer, ProjectSession]:
    container = LfprojContainer(tmp_path / "work")
    session = container.create({"project_name": "Dialog"})
    repository = SQLiteProjectRepository(session.database_path)
    repository.create(
        Project(
            id="project-1",
            name="Dialog",
            source_language="en",
            target_language="ru",
            source_document={"text": "Hello"},
            entries=[TranslationEntry("entry-1", ("text",), "Hello")],
        )
    )
    return container, session


def test_save_then_open_restores_working_project(tmp_path: Path) -> None:
    container, session = create_project_session(tmp_path)
    destination = tmp_path / "dialog.lfproj"

    container.save(session, destination)
    opened_session = LfprojContainer(tmp_path / "opened").open(destination)

    restored = SQLiteProjectRepository(opened_session.database_path).get("project-1")
    assert restored.entries[0].source == "Hello"
    assert opened_session.metadata == {"project_name": "Dialog", "format_version": 2}
    assert opened_session.container_path == destination


def test_saving_existing_container_creates_a_backup(tmp_path: Path) -> None:
    container, session = create_project_session(tmp_path)
    destination = tmp_path / "dialog.lfproj"
    container.save(session, destination)
    first_archive = destination.read_bytes()

    session.metadata["project_name"] = "Updated dialog"
    container.save(session, destination)

    assert destination.with_suffix(".lfproj.bak").read_bytes() == first_archive


def test_saving_existing_container_rotates_three_backup_generations(tmp_path: Path) -> None:
    container, session = create_project_session(tmp_path)
    destination = tmp_path / "dialog.lfproj"
    saved_versions: list[bytes] = []

    for version in range(4):
        session.metadata["version"] = version
        container.save(session, destination)
        saved_versions.append(destination.read_bytes())

    assert destination.with_suffix(".lfproj.bak").read_bytes() == saved_versions[2]
    assert destination.with_suffix(".lfproj.bak.1").read_bytes() == saved_versions[1]
    assert destination.with_suffix(".lfproj.bak.2").read_bytes() == saved_versions[0]
    assert not destination.with_suffix(".lfproj.bak.3").exists()


def test_saving_snapshot_restores_working_project_without_creating_backup(tmp_path: Path) -> None:
    container, session = create_project_session(tmp_path)
    destination = tmp_path / "dialog.lfproj"

    container.save_snapshot(session, destination)
    opened_session = LfprojContainer(tmp_path / "opened").open(destination)

    assert SQLiteProjectRepository(opened_session.database_path).get("project-1").name == "Dialog"
    assert not destination.with_suffix(".lfproj.bak").exists()


def test_open_upgrades_version_one_container_metadata(tmp_path: Path) -> None:
    _, session = create_project_session(tmp_path)
    legacy_container = tmp_path / "legacy.lfproj"
    with zipfile.ZipFile(legacy_container, "w") as archive:
        archive.write(session.database_path, "project.db")
        archive.writestr(
            "metadata.json",
            '{"format_version": 1, "project_id": "project-1"}',
        )

    opened = LfprojContainer(tmp_path / "opened").open(legacy_container)

    assert opened.metadata["format_version"] == 2
    assert SQLiteProjectRepository(opened.database_path).get("project-1").name == "Dialog"


def test_open_rejects_container_without_project_database(tmp_path: Path) -> None:
    broken_container = tmp_path / "broken.lfproj"
    with zipfile.ZipFile(broken_container, "w") as archive:
        archive.writestr("metadata.json", '{"format_version": 1}')

    with pytest.raises(ProjectContainerError, match="project.db"):
        LfprojContainer(tmp_path / "work").open(broken_container)


def test_open_rejects_unsafe_archive_member(tmp_path: Path) -> None:
    unsafe_container = tmp_path / "unsafe.lfproj"
    with zipfile.ZipFile(unsafe_container, "w") as archive:
        archive.writestr("metadata.json", '{"format_version": 1}')
        archive.writestr("project.db", "database")
        archive.writestr("../unsafe.txt", "unsafe")

    with pytest.raises(ProjectContainerError, match="unsafe"):
        LfprojContainer(tmp_path / "work").open(unsafe_container)


def test_open_rejects_container_with_corrupt_project_database(tmp_path: Path) -> None:
    broken_container = tmp_path / "broken-database.lfproj"
    with zipfile.ZipFile(broken_container, "w") as archive:
        archive.writestr("metadata.json", '{"format_version": 2}')
        archive.writestr("project.db", b"not a sqlite database")

    with pytest.raises(ProjectContainerError, match="integrity"):
        LfprojContainer(tmp_path / "work").open(broken_container)


def test_save_rejects_corrupt_database_without_replacing_existing_container(
    tmp_path: Path,
) -> None:
    container, session = create_project_session(tmp_path)
    destination = tmp_path / "dialog.lfproj"
    container.save(session, destination)
    saved_container = destination.read_bytes()
    session.database_path.write_bytes(b"not a sqlite database")

    with pytest.raises(ProjectContainerError, match="integrity"):
        container.save(session, destination)

    assert destination.read_bytes() == saved_container
    assert not destination.with_suffix(".lfproj.tmp").exists()

from pathlib import Path

import pytest

from locaforge.application.project_session import ProjectSession
from locaforge.application.services.project_persistence import ProjectPersistenceService
from locaforge.domain.project import Project


class Repository:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.marked_dirty: list[str] = []
        self.marked_saved: list[str] = []

    def get(self, _project_id: str) -> Project:
        return self.project

    def mark_project_dirty(self, project_id: str) -> None:
        self.marked_dirty.append(project_id)

    def mark_project_saved(self, project_id: str) -> None:
        self.marked_saved.append(project_id)


class Factory:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def create(self, _database_path: Path) -> Repository:
        return self.repository


class Container:
    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        self.opened: list[Path] = []
        self.snapshots: list[tuple[ProjectSession, Path]] = []

    def open(self, path: Path) -> ProjectSession:
        self.opened.append(path)
        return self.session

    def save_snapshot(self, session: ProjectSession, destination: Path) -> None:
        self.snapshots.append((session, destination))


def make_service(
    container: Container, repository: Repository
) -> ProjectPersistenceService:
    return ProjectPersistenceService(  # type: ignore[arg-type]
        container, Factory(repository)
    )


def test_opens_backup_as_dirty_unsaved_recovery_copy(tmp_path: Path) -> None:
    original = tmp_path / "demo.lfproj"
    project = Project("p", "Demo", "en", "ru")
    session = ProjectSession(
        tmp_path / "work",
        tmp_path / "project.db",
        {"project_id": project.id},
        original.with_suffix(".lfproj.bak"),
    )
    repository = Repository(project)
    container = Container(session)

    opened = make_service(container, repository).open_backup(original)

    assert container.opened == [original.with_suffix(".lfproj.bak")]
    assert opened.session.container_path is None
    assert opened.session.metadata["recovered_from"] == str(original)
    assert opened.project.dirty is True
    assert repository.marked_dirty == [project.id]


def test_autosave_marks_saved_and_writes_snapshot(tmp_path: Path) -> None:
    destination = tmp_path / "demo.lfproj"
    project = Project("p", "Demo", "en", "ru")
    session = ProjectSession(
        tmp_path / "work",
        tmp_path / "project.db",
        {"project_id": project.id},
        destination,
    )
    repository = Repository(project)
    container = Container(session)

    make_service(container, repository).autosave(  # type: ignore[arg-type]
        repository, session, project
    )

    assert repository.marked_saved == [project.id]
    assert container.snapshots == [(session, destination)]


def test_autosave_rejects_unsaved_project_before_repository_change(
    tmp_path: Path,
) -> None:
    project = Project("p", "Demo", "en", "ru")
    session = ProjectSession(
        tmp_path / "work", tmp_path / "project.db", {"project_id": project.id}
    )
    repository = Repository(project)
    container = Container(session)

    with pytest.raises(ValueError, match="destination"):
        make_service(container, repository).autosave(  # type: ignore[arg-type]
            repository, session, project
        )

    assert repository.marked_saved == []
    assert container.snapshots == []

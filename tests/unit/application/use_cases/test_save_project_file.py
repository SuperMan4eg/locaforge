from pathlib import Path

import pytest

from locaforge.application.project_session import ProjectSession
from locaforge.application.use_cases.save_project_file import SaveProjectFile
from locaforge.domain.project import Project


class Repository:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.marked_saved: list[str] = []
        self.marked_dirty: list[str] = []

    def get(self, project_id: str) -> Project:
        assert project_id == self.project.id
        return self.project

    def mark_project_saved(self, project_id: str) -> None:
        self.marked_saved.append(project_id)

    def mark_project_dirty(self, project_id: str) -> None:
        self.marked_dirty.append(project_id)


class Factory:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def create(self, _database_path: Path) -> Repository:
        return self.repository


class Container:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.saved: list[tuple[ProjectSession, Path]] = []

    def save(self, session: ProjectSession, destination: Path) -> None:
        self.saved.append((session, destination))
        if self.error is not None:
            raise self.error


def make_session(tmp_path: Path, project: Project) -> ProjectSession:
    return ProjectSession(
        tmp_path / "work",
        tmp_path / "project.db",
        {"project_id": project.id},
        tmp_path / "demo.lfproj",
    )


def test_save_only_updates_dirty_flag_before_writing_container(tmp_path: Path) -> None:
    project = Project("p", "Demo", "en", "ru", dirty=True)
    repository = Repository(project)
    container = Container()
    session = make_session(tmp_path, project)

    saved = SaveProjectFile(container, Factory(repository)).execute(session)  # type: ignore[arg-type]

    assert saved is project
    assert saved.dirty is False
    assert repository.marked_saved == [project.id]
    assert repository.marked_dirty == []
    assert container.saved == [(session, session.container_path)]


def test_failed_container_save_restores_dirty_flag(tmp_path: Path) -> None:
    project = Project("p", "Demo", "en", "ru", dirty=True)
    repository = Repository(project)
    container = Container(RuntimeError("disk full"))
    session = make_session(tmp_path, project)

    with pytest.raises(RuntimeError, match="disk full"):
        SaveProjectFile(container, Factory(repository)).execute(session)  # type: ignore[arg-type]

    assert project.dirty is True
    assert repository.marked_saved == [project.id]
    assert repository.marked_dirty == [project.id]

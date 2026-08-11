from pathlib import Path

import pytest

from locaforge.application.project_session import ProjectSession
from locaforge.application.services.project_creation import ProjectCreationService
from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile


class Repository:
    def __init__(self) -> None:
        self.created: list[Project] = []

    def create(self, project: Project) -> None:
        self.created.append(project)


class RepositoryFactory:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        self.paths: list[Path] = []

    def create(self, database_path: Path) -> Repository:
        self.paths.append(database_path)
        return self.repository


class Container:
    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        self.metadata: dict[str, object] | None = None
        self.saved: list[tuple[ProjectSession, Path]] = []

    def create(self, metadata: dict[str, object] | None = None) -> ProjectSession:
        self.metadata = metadata
        return self.session

    def save(self, session: ProjectSession, destination: Path) -> None:
        self.saved.append((session, destination))


def test_creates_empty_portable_project(tmp_path: Path) -> None:
    session = ProjectSession(tmp_path / "work", tmp_path / "project.db", {})
    repository = Repository()
    factory = RepositoryFactory(repository)
    container = Container(session)
    service = ProjectCreationService(container, factory)  # type: ignore[arg-type]
    destination = tmp_path / "demo.lfproj"
    profile = ProjectProfile(description="Demo profile")

    created = service.create(destination, " Demo ", " en ", " ru ", profile)

    assert created.project.name == "Demo"
    assert created.project.source_language == "en"
    assert created.project.target_language == "ru"
    assert created.project.profile == profile
    assert created.project.documents == []
    assert created.project.entries == []
    assert repository.created == [created.project]
    assert factory.paths == [session.database_path]
    assert container.saved == [(session, destination)]
    assert container.metadata == {
        "project_id": created.project.id,
        "project_name": "Demo",
        "source_files": [],
        "source_format": "multiple",
        "source_language": "en",
        "target_language": "ru",
    }


def test_rejects_non_project_destination_before_creating_session(tmp_path: Path) -> None:
    session = ProjectSession(tmp_path / "work", tmp_path / "project.db", {})
    repository = Repository()
    container = Container(session)
    service = ProjectCreationService(  # type: ignore[arg-type]
        container, RepositoryFactory(repository)
    )

    with pytest.raises(ValueError, match=".lfproj"):
        service.create(tmp_path / "demo.zip", "Demo", "en", "ru")

    assert container.metadata is None
    assert repository.created == []

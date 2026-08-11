"""Creation of empty portable localization projects."""

from __future__ import annotations

import uuid
from pathlib import Path

from locaforge.application.dto.project import CreatedProject
from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile


class ProjectCreationService:
    """Create and persist a new project before source files are imported."""

    def __init__(
        self,
        project_container: ProjectContainer,
        repository_factory: ProjectRepositoryFactory,
    ) -> None:
        self._project_container = project_container
        self._repository_factory = repository_factory

    def create(
        self,
        destination: Path,
        name: str,
        source_language: str,
        target_language: str,
        profile: ProjectProfile | None = None,
    ) -> CreatedProject:
        if destination.suffix.lower() != ".lfproj":
            raise ValueError("Project destination must use the .lfproj extension")
        project = Project(
            id=str(uuid.uuid4()),
            name=name.strip(),
            source_language=source_language.strip(),
            target_language=target_language.strip(),
            profile=profile or ProjectProfile(),
        )
        session = self._project_container.create(
            {
                "project_id": project.id,
                "project_name": project.name,
                "source_files": [],
                "source_format": "multiple",
                "source_language": project.source_language,
                "target_language": project.target_language,
            }
        )
        repository = self._repository_factory.create(session.database_path)
        repository.create(project)
        self._project_container.save(session, destination)
        return CreatedProject(project, session)

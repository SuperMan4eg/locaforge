"""Update model settings for an open project."""

from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings


class UpdateModelSettings:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self._project_repository = project_repository

    def execute(self, project_id: str, settings: ModelSettings) -> Project:
        project = self._project_repository.get(project_id)
        project.update_model_settings(settings)
        self._project_repository.save(project)
        return project

"""Effective model settings and local LLM backend operations."""

from __future__ import annotations

from locaforge.application.errors import ModelUnavailableError
from locaforge.application.ports.llm import LLMClient
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.use_cases.update_model_settings import UpdateModelSettings
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings


class ModelConfigurationService:
    """Own global settings and coordinate project-specific model overrides."""

    def __init__(self, llm_client: LLMClient | None) -> None:
        self._llm_client = llm_client
        self._global_settings = ModelSettings()

    @property
    def global_settings(self) -> ModelSettings:
        return self._global_settings

    def set_global_settings(self, settings: ModelSettings) -> None:
        self._global_settings = settings

    def resolve(self, project: Project | None = None) -> ModelSettings:
        if project is not None and project.model_settings_override_enabled:
            return project.model_settings
        return self._global_settings

    @staticmethod
    def source(project: Project) -> str:
        return "project" if project.model_settings_override_enabled else "global"

    def set_llm_client(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def list_models(self) -> tuple[str, ...]:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        return self._llm_client.list_models()

    def health_check(self) -> bool:
        return self._llm_client is not None and self._llm_client.health_check()

    def pull_model(self, model: str) -> None:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        self._llm_client.pull_model(model)

    @staticmethod
    def update_project_settings(
        repository: ProjectRepository, project: Project, settings: ModelSettings
    ) -> Project:
        return UpdateModelSettings(repository).execute(project.id, settings)

    def set_project_override(
        self, repository: ProjectRepository, project: Project, enabled: bool
    ) -> Project:
        stored = repository.get(project.id)
        if enabled and not stored.model_settings_override_enabled:
            stored.update_model_settings(self.resolve(stored))
        stored.set_model_settings_override_enabled(enabled)
        repository.save(stored)
        return stored

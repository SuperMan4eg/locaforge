"""Project profile generation and persistence."""

from __future__ import annotations

from locaforge.application.dto.project_description import ProjectDescriptionRequest
from locaforge.application.errors import ModelUnavailableError
from locaforge.application.ports.llm import LLMClient
from locaforge.application.ports.project_metadata_lookup import ProjectMetadataLookup
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.project_session import ProjectSession
from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile
from locaforge.domain.settings import ModelSettings


class ProjectProfileService:
    """Generate descriptive metadata and persist project-owned profile fields."""

    def __init__(
        self,
        llm_client: LLMClient | None,
        metadata_lookup: ProjectMetadataLookup | None,
    ) -> None:
        self._llm_client = llm_client
        self._metadata_lookup = metadata_lookup

    def set_llm_client(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def generate(
        self,
        name: str,
        settings: ModelSettings,
        *,
        use_online_lookup: bool = False,
    ) -> ProjectProfile:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Enter a project name before generating its description")
        research_context = ""
        if use_online_lookup:
            if self._metadata_lookup is None:
                raise ModelUnavailableError("Online project lookup is not configured")
            research_context = self._metadata_lookup.lookup(normalized_name)
        return self._llm_client.describe_project(
            ProjectDescriptionRequest(
                normalized_name,
                settings.model,
                settings.timeout_seconds,
                research_context,
            )
        ).profile

    @staticmethod
    def update(
        repository: ProjectRepository,
        session: ProjectSession,
        project: Project,
        name: str,
        source_language: str,
        target_language: str,
        profile: ProjectProfile,
    ) -> None:
        normalized_name = name.strip()
        normalized_source = source_language.strip()
        normalized_target = target_language.strip()
        if not normalized_name or not normalized_source or not normalized_target:
            raise ValueError("Project name and languages must not be empty")
        if normalized_source.casefold() == normalized_target.casefold():
            raise ValueError("Source and target languages must be different")
        project.name = normalized_name
        project.source_language = normalized_source
        project.target_language = normalized_target
        project.profile = profile
        project.dirty = True
        session.metadata.update(
            {
                "project_name": normalized_name,
                "source_language": normalized_source,
                "target_language": normalized_target,
            }
        )
        repository.save(project)

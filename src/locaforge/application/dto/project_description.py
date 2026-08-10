"""Structured project-description generation messages."""

from dataclasses import dataclass

from locaforge.domain.project_profile import ProjectProfile


@dataclass(frozen=True, slots=True)
class ProjectDescriptionRequest:
    name: str
    model: str
    timeout_seconds: float
    research_context: str = ""


@dataclass(frozen=True, slots=True)
class ProjectDescriptionResponse:
    profile: ProjectProfile

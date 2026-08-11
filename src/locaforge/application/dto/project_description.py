"""Structured project-description generation messages."""

from dataclasses import dataclass

from locaforge.application.dto.model_performance import ModelUsageMetrics
from locaforge.domain.project_profile import ProjectProfile


@dataclass(frozen=True, slots=True)
class ProjectDescriptionRequest:
    name: str
    model: str
    timeout_seconds: float
    research_context: str = ""
    keep_alive_seconds: int = 300


@dataclass(frozen=True, slots=True)
class ProjectDescriptionResponse:
    profile: ProjectProfile
    usage: ModelUsageMetrics = ModelUsageMetrics()

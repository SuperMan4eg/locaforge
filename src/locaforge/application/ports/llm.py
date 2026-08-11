"""Interface for local translation model backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from locaforge.application.dto.model_performance import ModelPerformanceSnapshot
from locaforge.application.dto.project_description import (
    ProjectDescriptionRequest,
    ProjectDescriptionResponse,
)
from locaforge.application.dto.review import ReviewRequest, ReviewResponse
from locaforge.application.dto.translation import TranslationRequest, TranslationResponse


class LLMClient(Protocol):
    def health_check(self) -> bool: ...

    def list_models(self) -> tuple[str, ...]: ...

    def pull_model(self, model: str) -> None: ...

    def describe_project(
        self, request: ProjectDescriptionRequest
    ) -> ProjectDescriptionResponse: ...

    def translate(self, request: TranslationRequest) -> TranslationResponse: ...

    def review(self, request: ReviewRequest) -> ReviewResponse: ...


@runtime_checkable
class ModelPerformanceProvider(Protocol):
    """Optional capability implemented by model clients that expose safe metrics."""

    def performance_snapshot(self) -> ModelPerformanceSnapshot: ...

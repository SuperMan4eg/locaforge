"""Interface for local translation model backends."""

from __future__ import annotations

from typing import Protocol

from locaforge.application.dto.review import ReviewRequest, ReviewResponse
from locaforge.application.dto.translation import TranslationRequest, TranslationResponse


class LLMClient(Protocol):
    def health_check(self) -> bool: ...

    def list_models(self) -> tuple[str, ...]: ...

    def translate(self, request: TranslationRequest) -> TranslationResponse: ...

    def review(self, request: ReviewRequest) -> ReviewResponse: ...

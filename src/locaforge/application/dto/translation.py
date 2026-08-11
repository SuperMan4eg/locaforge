"""Immutable messages exchanged with translation services."""

from __future__ import annotations

from dataclasses import dataclass

from locaforge.application.dto.model_performance import ModelUsageMetrics


@dataclass(frozen=True, slots=True)
class TranslationRequestItem:
    entry_id: str
    source: str
    context: str | None = None


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    model: str
    source_language: str
    target_language: str
    entries: tuple[TranslationRequestItem, ...]
    prompt: str
    timeout_seconds: float
    reasoning: str = "off"
    keep_alive_seconds: int = 300


@dataclass(frozen=True, slots=True)
class TranslationResult:
    entry_id: str
    translation: str


@dataclass(frozen=True, slots=True)
class TranslationResponse:
    results: tuple[TranslationResult, ...]
    usage: ModelUsageMetrics = ModelUsageMetrics()


@dataclass(frozen=True, slots=True)
class BatchResult:
    translated_entry_ids: tuple[str, ...]
    skipped_entry_ids: tuple[str, ...]
    errors: tuple[str, ...]
    cancelled: bool = False

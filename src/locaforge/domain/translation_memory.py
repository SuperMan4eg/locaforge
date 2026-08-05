"""Translation memory domain values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranslationMemoryRecord:
    """A reusable translation for an exact source and optional context."""

    source_language: str
    target_language: str
    source: str
    translation: str
    context: str = ""

    def __post_init__(self) -> None:
        if not self.source_language.strip():
            raise ValueError("Source language must not be empty")
        if not self.target_language.strip():
            raise ValueError("Target language must not be empty")
        if not self.source:
            raise ValueError("Translation memory source must not be empty")
        if not self.translation:
            raise ValueError("Translation memory translation must not be empty")


@dataclass(frozen=True, slots=True)
class TranslationMemoryMatch:
    """A translation memory record ranked against a requested source."""

    record: TranslationMemoryRecord
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Translation memory score must be between 0 and 1")

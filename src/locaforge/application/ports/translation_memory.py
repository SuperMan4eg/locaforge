"""Translation memory persistence contract."""

from __future__ import annotations

from typing import Protocol

from locaforge.domain.translation_memory import (
    TranslationMemoryMatch,
    TranslationMemoryRecord,
)


class TranslationMemoryStore(Protocol):
    """Stores and retrieves exact translation memory records."""

    def store(self, record: TranslationMemoryRecord) -> None: ...

    def find_exact(
        self,
        source_language: str,
        target_language: str,
        source: str,
        context: str = "",
    ) -> TranslationMemoryRecord | None: ...

    def find_similar(
        self,
        source_language: str,
        target_language: str,
        source: str,
        context: str = "",
        limit: int = 5,
        minimum_score: float = 0.6,
    ) -> tuple[TranslationMemoryMatch, ...]: ...

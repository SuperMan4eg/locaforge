"""Glossary persistence contract."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from locaforge.domain.glossary import GlossaryTerm


class GlossaryStore(Protocol):
    """Stores terminology and finds terms relevant to source text."""

    def store(self, term: GlossaryTerm) -> None: ...

    def remove(self, term: GlossaryTerm) -> None: ...

    def list_terms(
        self,
        source_language: str,
        target_language: str,
    ) -> tuple[GlossaryTerm, ...]: ...

    def find_for_sources(
        self,
        source_language: str,
        target_language: str,
        sources: Sequence[str],
    ) -> tuple[GlossaryTerm, ...]: ...

    def find_for_sources_batch(
        self,
        source_language: str,
        target_language: str,
        sources: Sequence[str],
    ) -> tuple[tuple[GlossaryTerm, ...], ...]: ...

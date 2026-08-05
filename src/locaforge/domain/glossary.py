"""Glossary domain values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlossaryTerm:
    """A required source-to-target terminology mapping."""

    source_language: str
    target_language: str
    source: str
    target: str
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        if not self.source_language.strip():
            raise ValueError("Glossary source language must not be empty")
        if not self.target_language.strip():
            raise ValueError("Glossary target language must not be empty")
        if not self.source.strip():
            raise ValueError("Glossary source term must not be empty")
        if not self.target.strip():
            raise ValueError("Glossary target term must not be empty")

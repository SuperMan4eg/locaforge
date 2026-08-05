"""Business entities and invariants."""

from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.history import EntryRevision
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings
from locaforge.domain.translation_memory import (
    TranslationMemoryMatch,
    TranslationMemoryRecord,
)

__all__ = [
    "EntryStatus",
    "GlossaryTerm",
    "EntryRevision",
    "ModelSettings",
    "Project",
    "TranslationEntry",
    "TranslationMemoryMatch",
    "TranslationMemoryRecord",
]

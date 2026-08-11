"""LocaForge local-first translation platform."""

from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings

__version__ = "0.4.2"

__all__ = [
    "__version__",
    "EntryStatus",
    "ModelSettings",
    "Project",
    "ProjectDocument",
    "TranslationEntry",
]

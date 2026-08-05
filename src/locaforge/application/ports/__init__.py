"""Ports implemented by infrastructure adapters."""

from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.glossary_csv import GlossaryCsvFormat
from locaforge.application.ports.json_format import JsonExporter, JsonImporter
from locaforge.application.ports.llm import LLMClient
from locaforge.application.ports.project_container import ProjectContainer
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.project_repository_factory import ProjectRepositoryFactory
from locaforge.application.ports.translation_memory import TranslationMemoryStore

__all__ = [
    "JsonExporter",
    "JsonImporter",
    "GlossaryStore",
    "GlossaryCsvFormat",
    "LLMClient",
    "ProjectContainer",
    "ProjectRepository",
    "ProjectRepositoryFactory",
    "TranslationMemoryStore",
]

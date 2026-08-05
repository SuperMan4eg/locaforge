"""Factory port for project-scoped repositories."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from locaforge.application.ports.project_repository import ProjectRepository


class ProjectRepositoryFactory(Protocol):
    def create(self, database_path: Path) -> ProjectRepository: ...

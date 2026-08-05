"""Port for portable project containers."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from locaforge.application.project_session import ProjectSession


class ProjectContainer(Protocol):
    def create(self, metadata: dict[str, object] | None = None) -> ProjectSession: ...

    def open(self, path: Path) -> ProjectSession: ...

    def save(self, session: ProjectSession, destination: Path) -> None: ...

    def save_snapshot(self, session: ProjectSession, destination: Path) -> None: ...

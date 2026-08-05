"""A project's unpacked working copy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ProjectSession:
    """Paths and metadata required while a portable project is open."""

    working_directory: Path
    database_path: Path
    metadata: dict[str, object]
    container_path: Path | None = None

    @property
    def project_id(self) -> str:
        project_id = self.metadata.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("Project session metadata has no valid project_id")
        return project_id

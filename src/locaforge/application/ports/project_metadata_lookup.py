"""Optional online metadata lookup port."""

from typing import Protocol


class ProjectMetadataLookup(Protocol):
    def lookup(self, project_name: str) -> str: ...

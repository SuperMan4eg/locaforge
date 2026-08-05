"""DTOs returned by project lifecycle use cases."""

from dataclasses import dataclass

from locaforge.application.project_session import ProjectSession
from locaforge.domain.project import Project


@dataclass(frozen=True, slots=True)
class CreatedProject:
    project: Project
    session: ProjectSession


@dataclass(frozen=True, slots=True)
class OpenedProject:
    project: Project
    session: ProjectSession


@dataclass(frozen=True, slots=True)
class ExportPreflight:
    untranslated_entries: int
    entries_with_issues: int

    @property
    def has_warnings(self) -> bool:
        return self.untranslated_entries > 0 or self.entries_with_issues > 0


@dataclass(frozen=True, slots=True)
class ProjectStatistics:
    total_entries: int
    untranslated_entries: int
    translated_entries: int
    needs_review_entries: int
    approved_entries: int
    error_entries: int
    locked_entries: int
    entries_with_issues: int

    @property
    def completion_percent(self) -> int:
        if self.total_entries == 0:
            return 0
        return round(self.translated_entries / self.total_entries * 100)

"""Read-only project summaries calculated outside the workspace facade."""

from __future__ import annotations

from collections.abc import Iterable

from locaforge.application.dto.project import ExportPreflight, ProjectStatistics
from locaforge.application.dto.validation import EntryValidationIssue
from locaforge.domain.entry import EntryStatus
from locaforge.domain.project import Project


class ProjectReportingService:
    """Build presentation-ready summaries from project and validation state."""

    def export_preflight(
        self,
        project: Project,
        validation_issues: Iterable[EntryValidationIssue],
    ) -> ExportPreflight:
        entries_with_issues = {issue.entry_id for issue in validation_issues}
        return ExportPreflight(
            untranslated_entries=sum(
                entry.translation is None for entry in project.entries
            ),
            entries_with_issues=len(entries_with_issues),
        )

    def statistics(
        self,
        project: Project,
        validation_issues: Iterable[EntryValidationIssue],
    ) -> ProjectStatistics:
        entries = project.entries
        entries_with_issues = {issue.entry_id for issue in validation_issues}
        return ProjectStatistics(
            total_entries=len(entries),
            untranslated_entries=sum(
                entry.status is EntryStatus.UNTRANSLATED for entry in entries
            ),
            translated_entries=sum(entry.translation is not None for entry in entries),
            needs_review_entries=sum(
                entry.status is EntryStatus.NEEDS_REVIEW for entry in entries
            ),
            approved_entries=sum(
                entry.status is EntryStatus.APPROVED for entry in entries
            ),
            error_entries=sum(entry.status is EntryStatus.ERROR for entry in entries),
            locked_entries=sum(entry.locked for entry in entries),
            entries_with_issues=len(entries_with_issues),
        )

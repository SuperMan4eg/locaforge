"""Dismiss AI review findings for multiple entries at once."""

from collections.abc import Sequence

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.ports.project_repository import ProjectRepository


class DismissAiReviewIssues:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def execute(self, project_id: str, entry_ids: Sequence[str]) -> int:
        selected_entry_ids = frozenset(entry_ids)
        issues_by_entry: dict[str, list[ValidationIssue]] = {}
        dismissed_count = 0
        for issue in self._repository.list_validation_issues(project_id):
            if issue.entry_id not in selected_entry_ids:
                continue
            if issue.code is ValidationCode.AI_REVIEW:
                dismissed_count += 1
                issues_by_entry.setdefault(issue.entry_id, [])
                continue
            issues_by_entry.setdefault(issue.entry_id, []).append(
                ValidationIssue(issue.code, issue.message)
            )
        if not dismissed_count:
            return 0
        self._repository.replace_validation_issues_bulk(project_id, issues_by_entry)
        self._repository.mark_project_dirty(project_id)
        return dismissed_count

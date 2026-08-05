"""Dismiss an AI review finding while preserving deterministic validation issues."""

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.ports.project_repository import ProjectRepository


class DismissAiReviewIssue:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def execute(self, project_id: str, entry_id: str) -> None:
        remaining = tuple(
            ValidationIssue(issue.code, issue.message)
            for issue in self._repository.list_validation_issues(project_id)
            if issue.entry_id == entry_id and issue.code is not ValidationCode.AI_REVIEW
        )
        self._repository.replace_validation_issues(project_id, entry_id, remaining)
        self._repository.mark_project_dirty(project_id)

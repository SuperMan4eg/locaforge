"""Undoable dismissal of AI review validation issues."""

from __future__ import annotations

from collections.abc import Sequence

from locaforge.application.dto.validation import ValidationCode
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.services.project_history import ProjectHistoryService
from locaforge.application.use_cases.dismiss_ai_review_issue import DismissAiReviewIssue
from locaforge.application.use_cases.dismiss_ai_review_issues import DismissAiReviewIssues
from locaforge.domain.project import Project


class ReviewIssueService:
    """Dismiss AI findings and retain enough state to undo meaningful changes."""

    def dismiss_one(
        self, repository: ProjectRepository, project: Project, entry_id: str
    ) -> None:
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, (entry_id,)
        )
        had_ai_issue = any(
            issue.code is ValidationCode.AI_REVIEW
            for issue in previous_issues[entry_id]
        )
        DismissAiReviewIssue(repository).execute(project.id, entry_id)
        if had_ai_issue:
            repository.record_translation_operation(
                project.id,
                previous_entries,
                previous_issues,
                "Dismiss AI review issue",
            )

    def dismiss_many(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_ids: Sequence[str],
    ) -> int:
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, entry_ids
        )
        affected_entry_ids = tuple(
            entry_id
            for entry_id, issues in previous_issues.items()
            if any(issue.code is ValidationCode.AI_REVIEW for issue in issues)
        )
        dismissed_count = DismissAiReviewIssues(repository).execute(
            project.id, entry_ids
        )
        if dismissed_count:
            history.record_updated_entries(
                repository,
                project.id,
                affected_entry_ids,
                previous_entries,
                previous_issues,
                "Dismiss AI review issues",
            )
        return dismissed_count

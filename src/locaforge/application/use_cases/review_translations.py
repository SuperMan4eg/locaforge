"""Run a local AI review without modifying translations."""

from collections.abc import Sequence

from locaforge.application.dto.review import ReviewRequest, ReviewRequestItem
from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.ports.llm import LLMClient
from locaforge.application.ports.project_repository import ProjectRepository


class ReviewTranslations:
    def __init__(self, repository: ProjectRepository, llm_client: LLMClient) -> None:
        self._repository = repository
        self._llm_client = llm_client

    def execute(
        self,
        project_id: str,
        entry_ids: Sequence[str],
        model: str,
        timeout: float,
        review_prompt: str = "",
    ) -> int:
        project = self._repository.get(project_id)
        entries = [
            project.get_entry(entry_id)
            for entry_id in entry_ids
            if project.get_entry(entry_id).translation is not None
        ]
        response = self._llm_client.review(
            ReviewRequest(
                model,
                project.source_language,
                project.target_language,
                tuple(
                    ReviewRequestItem(entry.id, entry.source, entry.translation or "")
                    for entry in entries
                ),
                timeout,
                review_prompt,
            )
        )
        reviewed = {result.entry_id: result.issue for result in response.results}
        existing_by_entry: dict[str, list[ValidationIssue]] = {}
        for validation_issue in self._repository.list_validation_issues(project_id):
            if validation_issue.code is ValidationCode.AI_REVIEW:
                continue
            existing_by_entry.setdefault(validation_issue.entry_id, []).append(
                ValidationIssue(validation_issue.code, validation_issue.message)
            )
        for entry in entries:
            existing = tuple(existing_by_entry.get(entry.id, ()))
            issue = reviewed.get(entry.id)
            review_issue = (
                (ValidationIssue(ValidationCode.AI_REVIEW, issue),) if issue else ()
            )
            self._repository.replace_validation_issues(
                project_id,
                entry.id,
                (*existing, *review_issue),
            )
        if entries:
            self._repository.mark_project_dirty(project_id)
        return sum(reviewed.get(entry.id) is not None for entry in entries)

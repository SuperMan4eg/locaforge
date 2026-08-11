"""Batch AI review orchestration for translated entries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from locaforge.application.dto.review import ReviewBatchResult
from locaforge.application.errors import ModelUnavailableError
from locaforge.application.ports.llm import LLMClient
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.services.project_history import ProjectHistoryService
from locaforge.application.use_cases.review_translations import ReviewTranslations
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings

type ProgressCallback = Callable[[int, int], None]
type CancellationCheck = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class ReviewRun:
    result: ReviewBatchResult
    project_changed: bool


def _ignore_progress(completed: int, total: int) -> None:
    del completed, total


def _never_cancel() -> bool:
    return False


class TranslationReviewService:
    """Review translations in batches and persist one undoable operation."""

    def __init__(self, llm_client: LLMClient | None) -> None:
        self._llm_client = llm_client

    def set_llm_client(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def review(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_ids: Sequence[str],
        settings: ModelSettings,
        progress_callback: ProgressCallback | None = None,
        cancellation_check: CancellationCheck | None = None,
    ) -> ReviewRun:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        reviewer = ReviewTranslations(repository, self._llm_client)
        reviewable_ids = {
            entry_id
            for entry_id in entry_ids
            if repository.get_entry(project.id, entry_id).translation is not None
        }
        history = ProjectHistoryService()
        previous_entries, previous_issues = history.snapshot(
            repository, project.id, tuple(reviewable_ids)
        )
        report_progress = progress_callback or _ignore_progress
        is_cancelled = cancellation_check or _never_cancel
        reviewed_entries = 0
        changed_entry_ids: list[str] = []
        issue_count = 0
        cancelled = False
        report_progress(0, len(entry_ids))
        for offset in range(0, len(entry_ids), settings.batch_size):
            if is_cancelled():
                cancelled = True
                break
            batch_entry_ids = entry_ids[offset : offset + settings.batch_size]
            issue_count += reviewer.execute(
                project.id,
                batch_entry_ids,
                settings.effective_review_model,
                settings.timeout_seconds,
                settings.review_prompt,
                settings.review_reasoning,
            )
            changed_entry_ids.extend(
                entry_id for entry_id in batch_entry_ids if entry_id in reviewable_ids
            )
            reviewed_entries += len(batch_entry_ids)
            report_progress(reviewed_entries, len(entry_ids))
        history.record_updated_entries(
            repository,
            project.id,
            changed_entry_ids,
            previous_entries,
            previous_issues,
            "Review translations",
        )
        return ReviewRun(
            ReviewBatchResult(reviewed_entries, issue_count, cancelled),
            bool(changed_entry_ids),
        )

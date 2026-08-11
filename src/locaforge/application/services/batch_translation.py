"""Batch translation orchestration for an open project."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from locaforge.application.dto.translation import BatchResult
from locaforge.application.dto.validation import ValidationIssue
from locaforge.application.errors import ModelUnavailableError
from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.llm import LLMClient
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.use_cases.translate_batch import TranslateBatch
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings

type ProgressCallback = Callable[[int, int], None]
type CancellationCheck = Callable[[], bool]


def _ignore_progress(completed: int, total: int) -> None:
    del completed, total


def _never_cancel() -> bool:
    return False


class BatchTranslationService:
    """Translate entries in configured batches and record one undo operation."""

    def __init__(
        self,
        llm_client: LLMClient | None,
        translation_memory: TranslationMemoryStore | None,
        glossary: GlossaryStore | None,
    ) -> None:
        self._llm_client = llm_client
        self._translation_memory = translation_memory
        self._glossary = glossary

    def set_llm_client(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def translate(
        self,
        repository: ProjectRepository,
        project: Project,
        entry_ids: Sequence[str],
        settings: ModelSettings,
        model: str | None = None,
        progress_callback: ProgressCallback | None = None,
        cancellation_check: CancellationCheck | None = None,
    ) -> BatchResult:
        if self._llm_client is None:
            raise ModelUnavailableError("No LLM backend is configured")
        previous_entries = {
            entry_id: repository.get_entry(project.id, entry_id)
            for entry_id in entry_ids
        }
        previous_issues: dict[str, list[ValidationIssue]] = {}
        for issue in repository.list_validation_issues(project.id):
            if issue.entry_id in previous_entries:
                previous_issues.setdefault(issue.entry_id, []).append(
                    ValidationIssue(issue.code, issue.message)
                )
        selected_model = model or settings.model
        translated_entry_ids: list[str] = []
        skipped_entry_ids: list[str] = []
        errors: list[str] = []
        report_progress = progress_callback or _ignore_progress
        is_cancelled = cancellation_check or _never_cancel
        total_entries = len(entry_ids)
        completed_entries = 0
        cancelled = False
        report_progress(completed_entries, total_entries)
        for offset in range(0, len(entry_ids), settings.batch_size):
            if is_cancelled():
                cancelled = True
                break
            batch_entry_ids = entry_ids[offset : offset + settings.batch_size]
            result = TranslateBatch(
                repository,
                self._llm_client,
                translation_memory=self._translation_memory,
                glossary=self._glossary,
            ).execute(
                project.id,
                batch_entry_ids,
                selected_model,
                settings.timeout_seconds,
                settings.system_prompt,
                is_cancelled,
                settings.translation_reasoning,
            )
            translated_entry_ids.extend(result.translated_entry_ids)
            skipped_entry_ids.extend(result.skipped_entry_ids)
            errors.extend(result.errors)
            if result.cancelled:
                completed_entries += len(result.translated_entry_ids) + len(
                    result.skipped_entry_ids
                )
                report_progress(completed_entries, total_entries)
                cancelled = True
                break
            completed_entries += len(batch_entry_ids)
            report_progress(completed_entries, total_entries)
        changed_entry_ids = tuple(dict.fromkeys(translated_entry_ids))
        repository.record_translation_operation(
            project.id,
            tuple(previous_entries[entry_id] for entry_id in changed_entry_ids),
            previous_issues,
            "Translate entries",
        )
        return BatchResult(
            tuple(translated_entry_ids),
            tuple(skipped_entry_ids),
            tuple(errors),
            cancelled,
        )

"""Batch translation workflow."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

from locaforge.application.dto.translation import (
    BatchResult,
    TranslationRequest,
    TranslationRequestItem,
    TranslationResponse,
)
from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.errors import (
    InvalidModelResponseError,
    ModelTimeoutError,
    ModelUnavailableError,
    PlaceholderMismatchError,
)
from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.llm import LLMClient
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.services.glossary_validator import GlossaryValidator
from locaforge.application.services.placeholder_protector import PlaceholderProtector, ProtectedText
from locaforge.application.services.retry_policy import BatchRetryPolicy
from locaforge.application.services.translation_validator import TranslationValidator
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.glossary import GlossaryTerm

type CancellationCheck = Callable[[], bool]


def _never_cancel() -> bool:
    return False


class TranslateBatch:
    """Translates editable entries and stores each validated response independently."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        llm_client: LLMClient,
        placeholder_protector: PlaceholderProtector | None = None,
        translation_validator: TranslationValidator | None = None,
        retry_policy: BatchRetryPolicy | None = None,
        translation_memory: TranslationMemoryStore | None = None,
        glossary: GlossaryStore | None = None,
        glossary_validator: GlossaryValidator | None = None,
    ) -> None:
        self._project_repository = project_repository
        self._llm_client = llm_client
        self._placeholder_protector = placeholder_protector or PlaceholderProtector()
        self._translation_validator = translation_validator or TranslationValidator()
        self._retry_policy = retry_policy or BatchRetryPolicy()
        self._translation_memory = translation_memory
        self._glossary = glossary
        self._glossary_validator = glossary_validator or GlossaryValidator()

    def execute(
        self,
        project_id: str,
        entry_ids: Sequence[str],
        model: str,
        timeout_seconds: float = 120.0,
        system_prompt: str = "",
        cancellation_check: CancellationCheck | None = None,
    ) -> BatchResult:
        project = self._project_repository.get(project_id)
        selected_entries = [project.get_entry(entry_id) for entry_id in entry_ids]
        eligible_entries, skipped_entry_ids = self._split_eligible_entries(selected_entries)
        if not eligible_entries:
            return BatchResult((), tuple(skipped_entry_ids), ())

        translated_entry_ids: list[str] = []
        eligible_entries = self._apply_memory_matches(
            project_id,
            project.source_language,
            project.target_language,
            eligible_entries,
            translated_entry_ids,
        )
        if not eligible_entries:
            return BatchResult(tuple(translated_entry_ids), tuple(skipped_entry_ids), ())

        eligible_entries, duplicate_entries = self._deduplicate_entries(eligible_entries)
        protected_entries = {
            entry.id: self._placeholder_protector.protect(entry.source)
            for entry in eligible_entries
        }

        errors: list[str] = []
        cancelled = self._process_group(
            project_id=project_id,
            source_language=project.source_language,
            target_language=project.target_language,
            system_prompt=system_prompt,
            entries=eligible_entries,
            protected_entries=protected_entries,
            model=model,
            timeout_seconds=timeout_seconds,
            translated_entry_ids=translated_entry_ids,
            errors=errors,
            cancellation_check=cancellation_check or _never_cancel,
        )
        self._apply_duplicate_translations(
            project_id,
            project.source_language,
            project.target_language,
            eligible_entries,
            duplicate_entries,
            translated_entry_ids,
            errors,
        )
        return BatchResult(
            self._order_entry_ids(translated_entry_ids, entry_ids),
            tuple(skipped_entry_ids),
            tuple(errors),
            cancelled,
        )

    def _process_group(
        self,
        project_id: str,
        source_language: str,
        target_language: str,
        system_prompt: str,
        entries: Sequence[TranslationEntry],
        protected_entries: dict[str, ProtectedText],
        model: str,
        timeout_seconds: float,
        translated_entry_ids: list[str],
        errors: list[str],
        cancellation_check: CancellationCheck,
    ) -> bool:
        pending_entries = list(entries)
        failure_reasons: dict[str, str] = {}
        for _attempt in range(self._retry_policy.attempts_per_group):
            if cancellation_check():
                return True
            if not pending_entries:
                return False
            try:
                response = self._translate_group(
                    source_language,
                    target_language,
                    system_prompt,
                    pending_entries,
                    protected_entries,
                    model,
                    timeout_seconds,
                )
            except (ModelUnavailableError, ModelTimeoutError, InvalidModelResponseError) as error:
                failure_reasons = {entry.id: str(error) for entry in pending_entries}
                continue
            pending_entries, failure_reasons = self._apply_response(
                project_id,
                source_language,
                target_language,
                pending_entries,
                protected_entries,
                response,
                translated_entry_ids,
            )

        if not pending_entries:
            return False
        if len(pending_entries) > 1:
            midpoint = (len(pending_entries) + 1) // 2
            for subgroup in (pending_entries[:midpoint], pending_entries[midpoint:]):
                cancelled = self._process_group(
                    project_id,
                    source_language,
                    target_language,
                    system_prompt,
                    subgroup,
                    protected_entries,
                    model,
                    timeout_seconds,
                    translated_entry_ids,
                    errors,
                    cancellation_check,
                )
                if cancelled:
                    return True
            return False

        entry = pending_entries[0]
        reason = failure_reasons.get(entry.id, "Unknown translation failure")
        errors.append(f"Translation failed for entry {entry.id!r}: {reason}")
        entry.mark_error()
        self._project_repository.update_entry(project_id, entry)
        existing_issues = tuple(
            issue
            for issue in self._project_repository.list_validation_issues(project_id)
            if issue.entry_id == entry.id
        )
        if not existing_issues:
            self._project_repository.replace_validation_issues(
                project_id,
                entry.id,
                (ValidationIssue(ValidationCode.MODEL_RESPONSE, reason),),
            )
        return False

    def _translate_group(
        self,
        source_language: str,
        target_language: str,
        system_prompt: str,
        entries: Sequence[TranslationEntry],
        protected_entries: dict[str, ProtectedText],
        model: str,
        timeout_seconds: float,
    ) -> TranslationResponse:
        request_items = tuple(
            TranslationRequestItem(
                entry.id, protected_entries[entry.id].protected, entry.context
            )
            for entry in entries
        )
        request = TranslationRequest(
            model=model,
            source_language=source_language,
            target_language=target_language,
            entries=request_items,
            prompt=self._build_prompt(
                source_language,
                target_language,
                request_items,
                system_prompt,
                self._find_glossary_terms(
                    source_language, target_language, entries
                ),
            ),
            timeout_seconds=timeout_seconds,
        )
        return self._llm_client.translate(request)

    def _find_glossary_terms(
        self,
        source_language: str,
        target_language: str,
        entries: Sequence[TranslationEntry],
    ) -> tuple[GlossaryTerm, ...]:
        if self._glossary is None:
            return ()
        return self._glossary.find_for_sources(
            source_language,
            target_language,
            tuple(entry.source for entry in entries),
        )

    def _apply_response(
        self,
        project_id: str,
        source_language: str,
        target_language: str,
        entries: Sequence[TranslationEntry],
        protected_entries: dict[str, ProtectedText],
        response: TranslationResponse,
        translated_entry_ids: list[str],
    ) -> tuple[list[TranslationEntry], dict[str, str]]:
        expected_entries = {entry.id: entry for entry in entries}
        successful_entry_ids: set[str] = set()
        seen_result_ids: set[str] = set()
        failure_reasons: dict[str, str] = {}
        response_diagnostics: list[str] = []
        updated_entries: list[TranslationEntry] = []
        issues_by_entry: dict[str, tuple[ValidationIssue, ...]] = {}
        translations_to_store: list[tuple[TranslationEntry, str]] = []

        for result in response.results:
            entry = expected_entries.get(result.entry_id)
            if entry is None or result.entry_id in seen_result_ids:
                response_diagnostics.append(f"Unexpected or duplicate result {result.entry_id!r}")
                continue
            seen_result_ids.add(result.entry_id)
            try:
                translation = protected_entries[entry.id].restore(result.translation)
            except PlaceholderMismatchError as error:
                message = f"Invalid placeholders: {error}"
                failure_reasons[entry.id] = message
                entry.mark_error()
                updated_entries.append(entry)
                issues_by_entry[entry.id] = (
                    ValidationIssue(ValidationCode.PLACEHOLDER_MISMATCH, message),
                )
                continue
            validation_issues = self._validate_translation(
                source_language, target_language, entry, translation
            )
            if validation_issues:
                failure_reasons[entry.id] = "; ".join(
                    issue.message for issue in validation_issues
                )
                entry.mark_error()
                updated_entries.append(entry)
                issues_by_entry[entry.id] = validation_issues
                continue
            entry.mark_model_translation(translation)
            updated_entries.append(entry)
            issues_by_entry[entry.id] = ()
            translations_to_store.append((entry, translation))
            successful_entry_ids.add(entry.id)
            translated_entry_ids.append(entry.id)

        self._persist_entries(project_id, updated_entries, issues_by_entry)
        diagnostics = "; ".join(response_diagnostics)
        pending_entries = [entry for entry in entries if entry.id not in successful_entry_ids]
        for entry in pending_entries:
            reason = failure_reasons.get(entry.id, "Missing translation in model response")
            if diagnostics:
                reason = f"{reason}; {diagnostics}"
            failure_reasons[entry.id] = reason
        return pending_entries, failure_reasons

    def _apply_memory_matches(
        self,
        project_id: str,
        source_language: str,
        target_language: str,
        entries: Sequence[TranslationEntry],
        translated_entry_ids: list[str],
    ) -> list[TranslationEntry]:
        if self._translation_memory is None:
            return list(entries)
        pending_entries: list[TranslationEntry] = []
        updated_entries: list[TranslationEntry] = []
        issues_by_entry: dict[str, tuple[ValidationIssue, ...]] = {}
        for entry in entries:
            record = self._translation_memory.find_exact(
                source_language,
                target_language,
                entry.source,
                entry.context or "",
            )
            if record is None:
                pending_entries.append(entry)
                continue
            validation_issues = self._validate_translation(
                source_language,
                target_language,
                entry,
                record.translation,
            )
            if validation_issues:
                pending_entries.append(entry)
                continue
            entry.mark_model_translation(record.translation)
            updated_entries.append(entry)
            issues_by_entry[entry.id] = ()
            translated_entry_ids.append(entry.id)
        self._persist_entries(project_id, updated_entries, issues_by_entry)
        return pending_entries

    def _apply_duplicate_translations(
        self,
        project_id: str,
        source_language: str,
        target_language: str,
        representatives: Sequence[TranslationEntry],
        duplicate_entries: dict[str, tuple[TranslationEntry, ...]],
        translated_entry_ids: list[str],
        errors: list[str],
    ) -> None:
        successful_entry_ids = set(translated_entry_ids)
        updated_entries: list[TranslationEntry] = []
        issues_by_entry: dict[str, tuple[ValidationIssue, ...]] = {}
        translations_to_store: list[tuple[TranslationEntry, str]] = []
        for representative in representatives:
            if (
                representative.id not in successful_entry_ids
                or representative.translation is None
            ):
                continue
            for entry in duplicate_entries.get(representative.id, ()):
                validation_issues = self._validate_translation(
                    source_language,
                    target_language,
                    entry,
                    representative.translation,
                )
                if validation_issues:
                    entry.mark_error()
                    updated_entries.append(entry)
                    issues_by_entry[entry.id] = validation_issues
                    errors.append(
                        f"Reused translation failed for entry {entry.id!r}: "
                        + "; ".join(issue.message for issue in validation_issues)
                    )
                    continue
                entry.mark_model_translation(representative.translation)
                updated_entries.append(entry)
                issues_by_entry[entry.id] = ()
                translations_to_store.append((entry, representative.translation))
                translated_entry_ids.append(entry.id)
        self._persist_entries(project_id, updated_entries, issues_by_entry)
    def _persist_entries(
        self,
        project_id: str,
        entries: Sequence[TranslationEntry],
        issues_by_entry: dict[str, tuple[ValidationIssue, ...]],
    ) -> None:
        self._project_repository.update_entries(project_id, entries)
        self._project_repository.replace_validation_issues_bulk(
            project_id, issues_by_entry
        )

    @staticmethod
    def _deduplicate_entries(
        entries: Sequence[TranslationEntry],
    ) -> tuple[list[TranslationEntry], dict[str, tuple[TranslationEntry, ...]]]:
        groups: dict[tuple[str, str | None], list[TranslationEntry]] = {}
        for entry in entries:
            groups.setdefault((entry.source, entry.context), []).append(entry)
        representatives: list[TranslationEntry] = []
        duplicate_entries: dict[str, tuple[TranslationEntry, ...]] = {}
        for grouped_entries in groups.values():
            representative = min(
                grouped_entries,
                key=lambda entry: (
                    entry.max_length is None,
                    entry.max_length if entry.max_length is not None else 0,
                ),
            )
            representatives.append(representative)
            duplicates = tuple(
                entry for entry in grouped_entries if entry.id != representative.id
            )
            if duplicates:
                duplicate_entries[representative.id] = duplicates
        return representatives, duplicate_entries

    @staticmethod
    def _order_entry_ids(
        translated_entry_ids: Sequence[str], requested_entry_ids: Sequence[str]
    ) -> tuple[str, ...]:
        translated_ids = set(translated_entry_ids)
        return tuple(entry_id for entry_id in requested_entry_ids if entry_id in translated_ids)

    def _validate_translation(
        self,
        source_language: str,
        target_language: str,
        entry: TranslationEntry,
        translation: str,
    ) -> tuple[ValidationIssue, ...]:
        issues = list(
            self._translation_validator.validate(entry, translation, target_language)
        )
        terms = self._find_glossary_terms(
            source_language, target_language, (entry,)
        )
        issues.extend(
            self._glossary_validator.validate(entry.source, translation, terms)
        )
        return tuple(issues)

    @staticmethod
    def _split_eligible_entries(
        entries: Sequence[TranslationEntry],
    ) -> tuple[list[TranslationEntry], list[str]]:
        eligible_entries: list[TranslationEntry] = []
        skipped_entry_ids: list[str] = []
        for entry in entries:
            if entry.locked or entry.status is EntryStatus.APPROVED:
                skipped_entry_ids.append(entry.id)
            else:
                eligible_entries.append(entry)
        return eligible_entries, skipped_entry_ids

    @staticmethod
    def _build_prompt(
        source_language: str,
        target_language: str,
        entries: Sequence[TranslationRequestItem],
        system_prompt: str = "",
        glossary_terms: Sequence[GlossaryTerm] = (),
    ) -> str:
        batch = [
            {"entry_id": entry.entry_id, "source": entry.source, "context": entry.context}
            for entry in entries
        ]
        translation_prompt = (
            f"Translate from {source_language} to {target_language}. "
            "Return only valid JSON with this exact shape: "
            '{"translations":[{"entry_id":"...","translation":"..."}]}. '
            "Keep entry_id and every __LF_PH_*__ token unchanged."
        )
        if glossary_terms:
            terminology = [
                {"source": term.source, "target": term.target}
                for term in glossary_terms
            ]
            translation_prompt += (
                "\n\nRequired terminology (use each target term consistently):\n"
                f"{json.dumps(terminology, ensure_ascii=False)}"
            )
        translation_prompt += (
            "\n\n"
            f"Batch:\n{json.dumps(batch, ensure_ascii=False)}"
        )
        if system_prompt.strip():
            return f"{system_prompt.strip()}\n\n{translation_prompt}"
        return translation_prompt

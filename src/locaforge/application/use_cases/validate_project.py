"""Revalidate all translated entries in a project."""

from __future__ import annotations

from collections import Counter

from locaforge.application.dto.validation import (
    ProjectValidationResult,
    ValidationCode,
    ValidationIssue,
)
from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.services.consistency_validator import ConsistencyValidator
from locaforge.application.services.glossary_validator import GlossaryValidator
from locaforge.application.services.placeholder_protector import PlaceholderProtector
from locaforge.application.services.translation_validator import TranslationValidator
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project


class ValidateProject:
    def __init__(
        self,
        project_repository: ProjectRepository,
        translation_validator: TranslationValidator | None = None,
        placeholder_protector: PlaceholderProtector | None = None,
        glossary: GlossaryStore | None = None,
        glossary_validator: GlossaryValidator | None = None,
        consistency_validator: ConsistencyValidator | None = None,
    ) -> None:
        self._project_repository = project_repository
        self._translation_validator = translation_validator or TranslationValidator()
        self._placeholder_protector = placeholder_protector or PlaceholderProtector()
        self._glossary = glossary
        self._glossary_validator = glossary_validator or GlossaryValidator()
        self._consistency_validator = consistency_validator or ConsistencyValidator()

    def execute(self, project_id: str) -> ProjectValidationResult:
        project = self._project_repository.get(project_id)
        existing_issues = self._existing_issues(project_id)
        consistency_issues = self._consistency_validator.validate(project.entries)
        entries_checked = 0
        entries_with_issues = 0
        issues_by_entry: dict[str, tuple[ValidationIssue, ...]] = {}
        entries_with_updated_statuses: list[TranslationEntry] = []
        for entry in project.entries:
            if entry.translation is None:
                continue
            entries_checked += 1
            issues = (
                *self._validate_entry(project, entry),
                *consistency_issues.get(entry.id, ()),
                *existing_issues.get(entry.id, ()),
            )
            issues_by_entry[entry.id] = issues
            has_blocking_issue = self._has_blocking_issue(issues)
            if issues:
                entries_with_issues += 1
                if has_blocking_issue and entry.status is not EntryStatus.ERROR:
                    entry.mark_error()
                    entries_with_updated_statuses.append(entry)
            if not has_blocking_issue and entry.status is EntryStatus.ERROR:
                entry.reopen_review()
                entries_with_updated_statuses.append(entry)
        self._project_repository.replace_validation_issues_bulk(
            project_id, issues_by_entry
        )
        self._project_repository.update_entry_statuses(
            project_id, entries_with_updated_statuses
        )
        return ProjectValidationResult(entries_checked, entries_with_issues)

    def _existing_issues(
        self, project_id: str
    ) -> dict[str, tuple[ValidationIssue, ...]]:
        issues_by_entry: dict[str, list[ValidationIssue]] = {}
        for issue in self._project_repository.list_validation_issues(project_id):
            if issue.code is ValidationCode.AI_REVIEW:
                issues_by_entry.setdefault(issue.entry_id, []).append(
                    ValidationIssue(issue.code, issue.message)
                )
        return {
            entry_id: tuple(issues)
            for entry_id, issues in issues_by_entry.items()
        }

    @staticmethod
    def _has_blocking_issue(issues: tuple[ValidationIssue, ...]) -> bool:
        return any(
            issue.code
            not in {ValidationCode.AI_REVIEW, ValidationCode.INCONSISTENT_TRANSLATION}
            for issue in issues
        )

    def _validate_entry(
        self,
        project: Project,
        entry: TranslationEntry,
    ) -> tuple[ValidationIssue, ...]:
        if entry.translation is None:
            return ()
        issues = list(
            self._translation_validator.validate(
                entry, entry.translation, project.target_language
            )
        )
        if Counter(self._placeholder_protector.extract(entry.source)) != Counter(
            self._placeholder_protector.extract(entry.translation)
        ):
            issues.append(
                ValidationIssue(
                    ValidationCode.PLACEHOLDER_MISMATCH,
                    "Translation must preserve all source placeholders",
                )
            )
        if self._glossary is not None:
            terms = self._glossary.find_for_sources(
                project.source_language,
                project.target_language,
                (entry.source,),
            )
            issues.extend(
                self._glossary_validator.validate(
                    entry.source, entry.translation, terms
                )
            )
        return tuple(issues)

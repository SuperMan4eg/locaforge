"""Manual translation editing workflow."""

from __future__ import annotations

from collections import Counter

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.ports.glossary import GlossaryStore
from locaforge.application.ports.project_repository import ProjectRepository
from locaforge.application.ports.translation_memory import TranslationMemoryStore
from locaforge.application.services.glossary_validator import GlossaryValidator
from locaforge.application.services.placeholder_protector import PlaceholderProtector
from locaforge.application.services.translation_validator import TranslationValidator
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.translation_memory import TranslationMemoryRecord


class EditTranslation:
    def __init__(
        self,
        project_repository: ProjectRepository,
        translation_validator: TranslationValidator | None = None,
        placeholder_protector: PlaceholderProtector | None = None,
        translation_memory: TranslationMemoryStore | None = None,
        glossary: GlossaryStore | None = None,
        glossary_validator: GlossaryValidator | None = None,
    ) -> None:
        self._project_repository = project_repository
        self._translation_validator = translation_validator or TranslationValidator()
        self._placeholder_protector = placeholder_protector or PlaceholderProtector()
        self._translation_memory = translation_memory
        self._glossary = glossary
        self._glossary_validator = glossary_validator or GlossaryValidator()

    def execute(self, project_id: str, entry_id: str, translation: str | None) -> TranslationEntry:
        project = self._project_repository.get(project_id)
        entry = project.set_entry_translation(entry_id, translation)
        issues = list(
            self._translation_validator.validate(entry, translation, project.target_language)
            if translation is not None
            else ()
        )
        if translation is not None and Counter(
            self._placeholder_protector.extract(entry.source)
        ) != Counter(self._placeholder_protector.extract(translation)):
            issues.append(
                ValidationIssue(
                    ValidationCode.PLACEHOLDER_MISMATCH,
                    "Translation must preserve all source placeholders",
                )
            )
        if translation is not None and self._glossary is not None:
            terms = self._glossary.find_for_sources(
                project.source_language,
                project.target_language,
                (entry.source,),
            )
            issues.extend(
                self._glossary_validator.validate(entry.source, translation, terms)
            )
        if issues:
            entry.mark_error()
        self._project_repository.update_entry(project_id, entry)
        self._project_repository.replace_validation_issues(project_id, entry.id, issues)
        if translation is not None and not issues and self._translation_memory is not None:
            self._translation_memory.store(
                TranslationMemoryRecord(
                    project.source_language,
                    project.target_language,
                    entry.source,
                    translation,
                    entry.context or "",
                )
            )
        return entry

"""Validation rules applied before a translation is persisted."""

from __future__ import annotations

import re
import unicodedata

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.domain.entry import TranslationEntry


class TranslationValidator:
    """Checks structural constraints relevant to software localization."""

    _LINE_BREAK_PATTERN = re.compile(r"\r\n|\r|\n")
    _CJK_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
    _ALLOWED_CONTROL_CHARACTERS = {"\n", "\r", "\t"}

    def validate(
        self, entry: TranslationEntry, translation: str, target_language: str = ""
    ) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        if entry.source.strip() and not translation.strip():
            issues.append(
                ValidationIssue(
                    ValidationCode.EMPTY_TRANSLATION,
                    "Translation is empty while the source contains text",
                )
            )
        normalized_source = entry.source.strip()
        normalized_translation = translation.strip()
        if (
            len(normalized_source) >= 3
            and normalized_source == normalized_translation
            and any(character.isalpha() for character in normalized_source)
        ):
            issues.append(
                ValidationIssue(
                    ValidationCode.SOURCE_TEXT_UNCHANGED,
                    "Translation is identical to the source text",
                )
            )
        if entry.max_length is not None and len(translation) > entry.max_length:
            issues.append(
                ValidationIssue(
                    ValidationCode.MAX_LENGTH_EXCEEDED,
                    f"Translation length {len(translation)} exceeds limit {entry.max_length}",
                )
            )

        source_line_breaks = len(self._LINE_BREAK_PATTERN.findall(entry.source))
        translation_line_breaks = len(self._LINE_BREAK_PATTERN.findall(translation))
        if source_line_breaks != translation_line_breaks:
            issues.append(
                ValidationIssue(
                    ValidationCode.LINE_BREAK_MISMATCH,
                    "Translation must preserve the number of line breaks",
                )
            )

        if any(unicodedata.category(character) == "Cs" for character in translation):
            issues.append(
                ValidationIssue(
                    ValidationCode.INVALID_UNICODE,
                    "Translation contains an unpaired Unicode surrogate",
                )
            )
        if any(
            unicodedata.category(character) == "Cc"
            and character not in self._ALLOWED_CONTROL_CHARACTERS
            for character in translation
        ):
            issues.append(
                ValidationIssue(
                    ValidationCode.CONTROL_CHARACTER,
                    "Translation contains a disallowed control character",
                )
            )
        if target_language.casefold().split("-", 1)[0] in {"en", "ru"} and self._CJK_PATTERN.search(
            translation
        ):
            issues.append(
                ValidationIssue(
                    ValidationCode.TARGET_LANGUAGE_MISMATCH,
                    "Translation contains CJK characters for a non-CJK target language",
                )
            )
        return tuple(issues)

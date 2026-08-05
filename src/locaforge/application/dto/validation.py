"""Structured validation results stored for project entries."""

from dataclasses import dataclass
from enum import StrEnum


class ValidationCode(StrEnum):
    EMPTY_TRANSLATION = "empty_translation"
    MAX_LENGTH_EXCEEDED = "max_length_exceeded"
    LINE_BREAK_MISMATCH = "line_break_mismatch"
    INVALID_UNICODE = "invalid_unicode"
    CONTROL_CHARACTER = "control_character"
    PLACEHOLDER_MISMATCH = "placeholder_mismatch"
    GLOSSARY_MISMATCH = "glossary_mismatch"
    MODEL_RESPONSE = "model_response"
    TARGET_LANGUAGE_MISMATCH = "target_language_mismatch"
    SOURCE_TEXT_UNCHANGED = "source_text_unchanged"
    INCONSISTENT_TRANSLATION = "inconsistent_translation"
    AI_REVIEW = "ai_review"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: ValidationCode
    message: str


@dataclass(frozen=True, slots=True)
class EntryValidationIssue:
    entry_id: str
    code: ValidationCode
    message: str


@dataclass(frozen=True, slots=True)
class ProjectValidationResult:
    entries_checked: int
    entries_with_issues: int

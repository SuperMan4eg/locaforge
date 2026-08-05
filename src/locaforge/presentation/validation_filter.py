"""Validation issue category filtering for the desktop UI."""

from collections.abc import Iterable
from dataclasses import dataclass

from locaforge.application.dto.validation import EntryValidationIssue, ValidationCode


@dataclass(frozen=True, slots=True)
class ValidationIssueGroup:
    entry_ids: tuple[str, ...]
    code: ValidationCode
    message: str


def filter_validation_issues(
    issues: Iterable[EntryValidationIssue], category: str | None
) -> tuple[EntryValidationIssue, ...]:
    if category == "attention":
        return tuple(issues)
    if category == "ai_review":
        return tuple(issue for issue in issues if issue.code is ValidationCode.AI_REVIEW)
    if category == "consistency":
        return tuple(
            issue
            for issue in issues
            if issue.code is ValidationCode.INCONSISTENT_TRANSLATION
        )
    if category == "structural":
        return tuple(
            issue
            for issue in issues
            if issue.code
            not in {ValidationCode.AI_REVIEW, ValidationCode.INCONSISTENT_TRANSLATION}
        )
    return tuple(issues)


def group_attention_issues(
    issues: Iterable[EntryValidationIssue],
) -> tuple[ValidationIssueGroup, ...]:
    """Group repeated consistency warnings while keeping other issues actionable."""
    groups: list[ValidationIssueGroup] = []
    consistency_positions: dict[tuple[ValidationCode, str], int] = {}
    for issue in issues:
        if issue.code is not ValidationCode.INCONSISTENT_TRANSLATION:
            groups.append(ValidationIssueGroup((issue.entry_id,), issue.code, issue.message))
            continue
        key = (issue.code, issue.message)
        position = consistency_positions.get(key)
        if position is None:
            consistency_positions[key] = len(groups)
            groups.append(ValidationIssueGroup((issue.entry_id,), issue.code, issue.message))
            continue
        group = groups[position]
        groups[position] = ValidationIssueGroup(
            (*group.entry_ids, issue.entry_id), group.code, group.message
        )
    return tuple(groups)


def format_validation_issues(issues: Iterable[EntryValidationIssue]) -> str:
    formatted = [f"[{issue.code.value}] {issue.message}" for issue in issues]
    return "\n".join(formatted) if formatted else "No validation issues"

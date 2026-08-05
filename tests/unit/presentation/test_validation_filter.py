from locaforge.application.dto.validation import EntryValidationIssue, ValidationCode
from locaforge.presentation.validation_filter import (
    filter_validation_issues,
    format_validation_issues,
    group_attention_issues,
)


def test_validation_filter_separates_ai_and_structural_issues() -> None:
    ai_issue = EntryValidationIssue("one", ValidationCode.AI_REVIEW, "Wrong meaning")
    structural_issue = EntryValidationIssue(
        "two", ValidationCode.PLACEHOLDER_MISMATCH, "Missing placeholder"
    )
    consistency_issue = EntryValidationIssue(
        "three", ValidationCode.INCONSISTENT_TRANSLATION, "Different variants"
    )
    issues = (ai_issue, structural_issue, consistency_issue)

    assert filter_validation_issues(issues, "ai_review") == (ai_issue,)
    assert filter_validation_issues(issues, "consistency") == (consistency_issue,)
    assert filter_validation_issues(issues, "structural") == (structural_issue,)
    assert filter_validation_issues(issues, None) == issues


def test_validation_formatter_shows_codes_and_empty_state() -> None:
    issue = EntryValidationIssue("one", ValidationCode.AI_REVIEW, "Wrong meaning")

    assert format_validation_issues((issue,)) == "[ai_review] Wrong meaning"
    assert format_validation_issues(()) == "No validation issues"


def test_attention_groups_repeated_consistency_conflicts() -> None:
    issues = (
        EntryValidationIssue(
            "one", ValidationCode.INCONSISTENT_TRANSLATION, "Two variants"
        ),
        EntryValidationIssue(
            "two", ValidationCode.INCONSISTENT_TRANSLATION, "Two variants"
        ),
        EntryValidationIssue("three", ValidationCode.AI_REVIEW, "Check meaning"),
    )

    groups = group_attention_issues(issues)

    assert groups[0].entry_ids == ("one", "two")
    assert groups[0].code is ValidationCode.INCONSISTENT_TRANSLATION
    assert groups[1].entry_ids == ("three",)

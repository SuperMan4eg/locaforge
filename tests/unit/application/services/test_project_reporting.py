from locaforge.application.dto.validation import EntryValidationIssue, ValidationCode
from locaforge.application.services.project_reporting import ProjectReportingService
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project


def make_project() -> Project:
    return Project(
        id="project-1",
        name="Game",
        source_language="en",
        target_language="ru",
        entries=[
            TranslationEntry("entry-1", ("first",), "First"),
            TranslationEntry(
                "entry-2",
                ("second",),
                "Second",
                translation="Второй",
                status=EntryStatus.APPROVED,
                locked=True,
            ),
            TranslationEntry(
                "entry-3",
                ("third",),
                "Third",
                translation="",
                status=EntryStatus.ERROR,
            ),
        ],
    )


def make_issues() -> tuple[EntryValidationIssue, ...]:
    return (
        EntryValidationIssue("entry-3", ValidationCode.EMPTY_TRANSLATION, "Empty"),
        EntryValidationIssue(
            "entry-3", ValidationCode.PLACEHOLDER_MISMATCH, "Placeholder"
        ),
    )


def test_calculates_statistics_and_counts_each_affected_entry_once() -> None:
    statistics = ProjectReportingService().statistics(make_project(), make_issues())

    assert statistics.total_entries == 3
    assert statistics.untranslated_entries == 1
    assert statistics.translated_entries == 2
    assert statistics.approved_entries == 1
    assert statistics.error_entries == 1
    assert statistics.locked_entries == 1
    assert statistics.entries_with_issues == 1
    assert statistics.completion_percent == 67


def test_calculates_export_preflight_from_translation_and_validation_state() -> None:
    preflight = ProjectReportingService().export_preflight(
        make_project(), make_issues()
    )

    assert preflight.untranslated_entries == 1
    assert preflight.entries_with_issues == 1
    assert preflight.has_warnings is True


def test_empty_project_has_zero_completion_and_no_export_warnings() -> None:
    project = Project("project-1", "Empty", "en", "ru", entries=[])
    service = ProjectReportingService()

    statistics = service.statistics(project, ())
    preflight = service.export_preflight(project, ())

    assert statistics.total_entries == 0
    assert statistics.completion_percent == 0
    assert preflight.has_warnings is False

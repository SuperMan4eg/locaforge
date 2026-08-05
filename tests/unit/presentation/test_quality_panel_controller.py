import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from typing import Any, cast

from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QListWidget, QPushButton

from locaforge.application.dto.validation import EntryValidationIssue, ValidationCode
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.presentation.quality_panel_controller import QualityPanelController


class ProjectStub:
    def __init__(self) -> None:
        self.entries = [
            TranslationEntry(
                "one",
                ("menu", "save"),
                "Save",
                "Сохранить",
                EntryStatus.NEEDS_REVIEW,
            ),
            TranslationEntry(
                "two",
                ("toolbar", "save"),
                "Save",
                "Записать",
                EntryStatus.NEEDS_REVIEW,
            ),
        ]

    def get_entry(self, entry_id: str) -> TranslationEntry:
        return next(entry for entry in self.entries if entry.id == entry_id)


class WorkspaceStub:
    has_project = True

    def __init__(self) -> None:
        self.project = ProjectStub()

    def validation_issues(self) -> tuple[EntryValidationIssue, ...]:
        return (
            EntryValidationIssue(
                "one", ValidationCode.INCONSISTENT_TRANSLATION, "Translations differ"
            ),
            EntryValidationIssue("one", ValidationCode.AI_REVIEW, "Check wording"),
        )


class TableFiltersStub:
    def __init__(self) -> None:
        self.entry_ids: tuple[str, ...] = ()

    def set_issue_entries(self, entry_ids: Any) -> None:
        self.entry_ids = tuple(entry_ids)


def make_controller() -> tuple[
    QualityPanelController,
    QListWidget,
    QLabel,
    tuple[QPushButton, QPushButton, QPushButton],
    TableFiltersStub,
    list[str],
]:
    category_filter = QComboBox()
    category_filter.addItem("All issues", None)
    issue_list = QListWidget()
    current_issues = QLabel()
    buttons = (QPushButton(), QPushButton(), QPushButton())
    table_filters = TableFiltersStub()
    selected: list[str] = []
    controller = QualityPanelController(
        workspace=cast(Any, WorkspaceStub()),
        category_filter=category_filter,
        issue_list=issue_list,
        current_issues=current_issues,
        dismiss_ai_button=buttons[0],
        retranslate_button=buttons[1],
        apply_matching_button=buttons[2],
        table_filters=cast(Any, table_filters),
        current_entry_id=lambda: "one",
        is_busy=lambda: False,
        select_entry=selected.append,
    )
    return controller, issue_list, current_issues, buttons, table_filters, selected


def test_refresh_populates_issues_and_current_entry_controls() -> None:
    application = QApplication.instance() or QApplication([])
    controller, issue_list, current_issues, buttons, table_filters, _ = make_controller()

    controller.refresh()

    assert application is not None
    assert issue_list.count() == 2
    assert table_filters.entry_ids == ("one",)
    assert "Translations differ" in current_issues.text()
    assert "Check wording" in current_issues.text()
    assert buttons[0].isEnabled() is True
    assert buttons[1].isEnabled() is True
    assert buttons[2].isEnabled() is True


def test_activated_issue_selects_its_entry() -> None:
    application = QApplication.instance() or QApplication([])
    controller, issue_list, _, _, _, selected = make_controller()
    controller.refresh()

    controller._activate_issue(issue_list.item(0))

    assert application is not None
    assert selected == ["one"]


def test_busy_state_disables_current_entry_actions() -> None:
    application = QApplication.instance() or QApplication([])
    category_filter = QComboBox()
    category_filter.addItem("All issues", None)
    issue_list = QListWidget()
    current_issues = QLabel()
    buttons = (QPushButton(), QPushButton(), QPushButton())
    controller = QualityPanelController(
        workspace=cast(Any, WorkspaceStub()),
        category_filter=category_filter,
        issue_list=issue_list,
        current_issues=current_issues,
        dismiss_ai_button=buttons[0],
        retranslate_button=buttons[1],
        apply_matching_button=buttons[2],
        table_filters=cast(Any, TableFiltersStub()),
        current_entry_id=lambda: "one",
        is_busy=lambda: True,
        select_entry=lambda entry_id: None,
    )

    controller.refresh()

    assert application is not None
    assert all(button.isEnabled() is False for button in buttons)

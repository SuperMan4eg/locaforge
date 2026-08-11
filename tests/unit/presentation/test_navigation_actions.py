import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow

from locaforge.presentation.navigation_actions import build_navigation_actions


def test_builds_navigation_menu_shortcuts_and_connects_callbacks() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[object] = []
    try:
        actions = build_navigation_actions(
            window,
            select_relative_entry=lambda offset: calls.append(("entry", offset)),
            select_relative_issue=lambda offset: calls.append(("issue", offset)),
            select_next_actionable_entry=lambda: calls.append("actionable"),
            focus_search=lambda: calls.append("search"),
            clear_filters=lambda: calls.append("filters"),
            select_all_visible=lambda: calls.append("all"),
            clear_project_selection=lambda: calls.append("escape"),
        )

        assert window.menuBar().actions()[0].text() == "&Navigate"
        assert actions.previous_entry.shortcut() == QKeySequence("Ctrl+Alt+Up")
        assert actions.next_issue.shortcut() == QKeySequence("F6")
        assert actions.focus_search.shortcut() == QKeySequence.StandardKey.Find
        actions.previous_entry.trigger()
        actions.next_issue.trigger()
        actions.next_actionable_entry.trigger()
        actions.focus_search.trigger()
        actions.clear_filters.trigger()
        actions.select_all_visible.trigger()
        actions.clear_project_selection.trigger()

        assert calls == [
            ("entry", -1),
            ("issue", 1),
            "actionable",
            "search",
            "filters",
            "all",
            "escape",
        ]
    finally:
        window.close()
        application.processEvents()

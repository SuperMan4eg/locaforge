"""Navigation menu and window-level shortcuts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu


@dataclass(frozen=True, slots=True)
class NavigationActions:
    menu: QMenu
    previous_entry: QAction
    next_entry: QAction
    previous_issue: QAction
    next_issue: QAction
    next_actionable_entry: QAction
    focus_search: QAction
    clear_filters: QAction
    select_all_visible: QAction
    clear_project_selection: QAction


def build_navigation_actions(
    window: QMainWindow,
    *,
    select_relative_entry: Callable[[int], None],
    select_relative_issue: Callable[[int], None],
    select_next_actionable_entry: Callable[[], None],
    focus_search: Callable[[], None],
    clear_filters: Callable[[], None],
    select_all_visible: Callable[[], None],
    clear_project_selection: Callable[[], None],
) -> NavigationActions:
    """Create the Navigate menu and register application shortcuts on the window."""
    menu = window.menuBar().addMenu("&Navigate")

    previous_entry = QAction("Previous entry", window)
    previous_entry.triggered.connect(lambda: select_relative_entry(-1))
    previous_entry.setShortcut(QKeySequence("Ctrl+Alt+Up"))
    window.addAction(previous_entry)

    next_entry = QAction("Next entry", window)
    next_entry.triggered.connect(lambda: select_relative_entry(1))
    next_entry.setShortcut(QKeySequence("Ctrl+Alt+Down"))
    window.addAction(next_entry)

    previous_issue = QAction("Previous issue", window)
    previous_issue.triggered.connect(lambda: select_relative_issue(-1))
    previous_issue.setShortcut(QKeySequence("Shift+F6"))
    window.addAction(previous_issue)

    next_issue = QAction("Next issue", window)
    next_issue.triggered.connect(lambda: select_relative_issue(1))
    next_issue.setShortcut(QKeySequence("F6"))
    window.addAction(next_issue)

    next_actionable_entry = QAction("Next actionable entry", window)
    next_actionable_entry.triggered.connect(select_next_actionable_entry)
    next_actionable_entry.setShortcut(QKeySequence("F7"))
    window.addAction(next_actionable_entry)

    focus_search_action = QAction("Focus search", window)
    focus_search_action.triggered.connect(focus_search)
    focus_search_action.setShortcut(QKeySequence.StandardKey.Find)
    window.addAction(focus_search_action)

    clear_filters_action = QAction("Clear table filters", window)
    clear_filters_action.triggered.connect(clear_filters)
    clear_filters_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
    window.addAction(clear_filters_action)

    select_all_visible_action = QAction("Select all visible", window)
    select_all_visible_action.setShortcut(QKeySequence.StandardKey.SelectAll)
    select_all_visible_action.triggered.connect(select_all_visible)
    window.addAction(select_all_visible_action)

    clear_project_selection_action = QAction(
        "Clear project filter or selection", window
    )
    clear_project_selection_action.setShortcut(QKeySequence("Esc"))
    clear_project_selection_action.triggered.connect(clear_project_selection)
    window.addAction(clear_project_selection_action)

    menu.addAction(previous_entry)
    menu.addAction(next_entry)
    menu.addSeparator()
    menu.addAction(previous_issue)
    menu.addAction(next_issue)
    menu.addAction(next_actionable_entry)
    menu.addSeparator()
    menu.addAction(focus_search_action)
    menu.addAction(clear_filters_action)

    return NavigationActions(
        menu,
        previous_entry,
        next_entry,
        previous_issue,
        next_issue,
        next_actionable_entry,
        focus_search_action,
        clear_filters_action,
        select_all_visible_action,
        clear_project_selection_action,
    )

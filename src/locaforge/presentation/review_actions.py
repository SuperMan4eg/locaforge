"""Review and QA menu actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu


@dataclass(frozen=True, slots=True)
class ReviewActions:
    menu: QMenu
    select_qa_entries: QAction
    retranslate_qa_entries: QAction
    dismiss_selected_ai_issues: QAction
    review_selected: QAction
    review_all: QAction
    approve_selected: QAction
    reopen_selected: QAction
    lock_selected: QAction
    unlock_selected: QAction


def build_review_actions(
    window: QMainWindow,
    *,
    select_qa_entries: Callable[[], None],
    retranslate_qa_entries: Callable[[], None],
    dismiss_selected_ai_issues: Callable[[], None],
    review_selected: Callable[[], None],
    review_all: Callable[[], None],
    approve_selected: Callable[[], None],
    reopen_selected: Callable[[], None],
    lock_selected: Callable[[], None],
    unlock_selected: Callable[[], None],
) -> ReviewActions:
    """Create the Review menu and connect each command to its handler."""
    menu = window.menuBar().addMenu("&Review")
    actions = ReviewActions(
        menu,
        QAction("Select all QA entries", window),
        QAction("Re-translate all QA entries", window),
        QAction("Dismiss AI issues for selected", window),
        QAction("AI review selected", window),
        QAction("AI review all Needs review", window),
        QAction("Approve selected", window),
        QAction("Reopen selected", window),
        QAction("Lock selected", window),
        QAction("Unlock selected", window),
    )
    actions.select_qa_entries.triggered.connect(select_qa_entries)
    actions.retranslate_qa_entries.triggered.connect(retranslate_qa_entries)
    actions.dismiss_selected_ai_issues.triggered.connect(dismiss_selected_ai_issues)
    actions.review_selected.triggered.connect(review_selected)
    actions.review_all.triggered.connect(review_all)
    actions.approve_selected.triggered.connect(approve_selected)
    actions.reopen_selected.triggered.connect(reopen_selected)
    actions.lock_selected.triggered.connect(lock_selected)
    actions.unlock_selected.triggered.connect(unlock_selected)

    menu.addAction(actions.select_qa_entries)
    menu.addAction(actions.retranslate_qa_entries)
    menu.addAction(actions.dismiss_selected_ai_issues)
    menu.addSeparator()
    menu.addAction(actions.review_selected)
    menu.addAction(actions.review_all)
    menu.addSeparator()
    menu.addAction(actions.approve_selected)
    menu.addAction(actions.reopen_selected)
    menu.addSeparator()
    menu.addAction(actions.lock_selected)
    menu.addAction(actions.unlock_selected)
    return actions

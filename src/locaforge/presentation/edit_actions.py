"""Edit menu actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu


@dataclass(frozen=True, slots=True)
class EditActions:
    menu: QMenu
    undo: QAction
    redo: QAction
    application_settings: QAction


def build_edit_actions(
    window: QMainWindow,
    *,
    undo: Callable[[], None],
    redo: Callable[[], None],
    open_application_settings: Callable[[], None],
) -> EditActions:
    """Create persistent-history and application-settings commands."""
    menu = window.menuBar().addMenu("&Edit")
    undo_action = QAction("Undo last operation", window)
    undo_action.setShortcut(QKeySequence.StandardKey.Undo)
    undo_action.setToolTip(
        "Restore entries changed by the latest editable operation (Ctrl+Z)"
    )
    undo_action.triggered.connect(undo)
    menu.addAction(undo_action)

    redo_action = QAction("Redo last operation", window)
    redo_action.setShortcut(QKeySequence.StandardKey.Redo)
    redo_action.setToolTip(
        "Reapply the latest undone editable operation (Ctrl+Shift+Z)"
    )
    redo_action.triggered.connect(redo)
    menu.addAction(redo_action)
    menu.addSeparator()

    settings_action = QAction("Settings...", window)
    settings_action.setShortcut(QKeySequence("Ctrl+,"))
    settings_action.triggered.connect(open_application_settings)
    menu.addAction(settings_action)
    return EditActions(menu, undo_action, redo_action, settings_action)

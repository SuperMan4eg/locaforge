"""Translation tools menu actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu


@dataclass(frozen=True, slots=True)
class ToolsActions:
    menu: QMenu
    translation_memory: QAction
    translate_all: QAction
    replace_translations: QAction
    validate_project: QAction
    apply_translation: QAction
    apply_and_next: QAction


def build_tools_actions(
    window: QMainWindow,
    *,
    open_translation_memory: Callable[[], None],
    translate_all: Callable[[], None],
    replace_translations: Callable[[], None],
    validate_project: Callable[[], None],
    apply_translation: Callable[[], object],
    apply_and_next: Callable[[], None],
) -> ToolsActions:
    """Create translation tool commands and editor-level shortcuts."""
    menu = window.menuBar().addMenu("&Tools")
    memory_action = QAction("Translation Memory...", window)
    memory_action.triggered.connect(open_translation_memory)
    menu.addAction(memory_action)
    menu.addSeparator()

    translate_all_action = QAction("Translate all untranslated", window)
    translate_all_action.triggered.connect(translate_all)
    translate_all_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
    menu.addAction(translate_all_action)

    replace_action = QAction("Replace translations...", window)
    replace_action.triggered.connect(replace_translations)
    replace_action.setShortcut(QKeySequence("Ctrl+H"))
    menu.addAction(replace_action)

    validate_action = QAction("Validate project", window)
    validate_action.triggered.connect(validate_project)
    validate_action.setShortcut(QKeySequence("F5"))
    menu.addAction(validate_action)

    apply_action = QAction("Apply current translation", window)
    apply_action.triggered.connect(apply_translation)
    apply_action.setShortcut(QKeySequence("Ctrl+Enter"))
    window.addAction(apply_action)

    apply_next_action = QAction("Apply and select next", window)
    apply_next_action.triggered.connect(apply_and_next)
    apply_next_action.setShortcut(QKeySequence("Ctrl+Shift+Enter"))
    window.addAction(apply_next_action)
    menu.addSeparator()
    menu.addAction(apply_action)
    menu.addAction(apply_next_action)

    return ToolsActions(
        menu,
        memory_action,
        translate_all_action,
        replace_action,
        validate_action,
        apply_action,
        apply_next_action,
    )

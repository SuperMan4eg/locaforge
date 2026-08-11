import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow

from locaforge.presentation.edit_actions import build_edit_actions


def test_builds_edit_actions_with_standard_shortcuts_and_callbacks() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[str] = []
    try:
        actions = build_edit_actions(
            window,
            undo=lambda: calls.append("undo"),
            redo=lambda: calls.append("redo"),
            open_application_settings=lambda: calls.append("settings"),
        )

        assert actions.undo.shortcut() == QKeySequence.StandardKey.Undo
        assert actions.redo.shortcut() == QKeySequence.StandardKey.Redo
        assert actions.application_settings.shortcut() == QKeySequence("Ctrl+,")
        actions.undo.trigger()
        actions.redo.trigger()
        actions.application_settings.trigger()
        assert calls == ["undo", "redo", "settings"]
    finally:
        window.close()
        application.processEvents()

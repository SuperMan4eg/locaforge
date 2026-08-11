import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow

from locaforge.presentation.tools_actions import build_tools_actions


def test_builds_tools_actions_and_registers_editor_shortcuts() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[str] = []
    try:
        actions = build_tools_actions(
            window,
            open_translation_memory=lambda: calls.append("memory"),
            translate_all=lambda: calls.append("translate"),
            replace_translations=lambda: calls.append("replace"),
            validate_project=lambda: calls.append("validate"),
            apply_translation=lambda: calls.append("apply"),
            apply_and_next=lambda: calls.append("next"),
        )

        assert actions.translate_all.shortcut() == QKeySequence("Ctrl+Shift+T")
        assert actions.validate_project.shortcut() == QKeySequence("F5")
        assert actions.apply_translation in window.actions()
        assert actions.apply_and_next in window.actions()
        actions.translation_memory.trigger()
        actions.translate_all.trigger()
        actions.replace_translations.trigger()
        actions.validate_project.trigger()
        actions.apply_translation.trigger()
        actions.apply_and_next.trigger()
        assert calls == ["memory", "translate", "replace", "validate", "apply", "next"]
    finally:
        window.close()
        application.processEvents()

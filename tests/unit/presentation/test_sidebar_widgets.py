import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QPushButton

from locaforge.presentation.sidebar_widgets import build_sidebar_widgets


def test_builds_and_arranges_all_sidebar_docks() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[str] = []
    try:
        sidebars = build_sidebar_widgets(
            window,
            copy_diagnostics=lambda: calls.append("diagnostics"),
        )

        assert {dock.windowTitle() for dock in sidebars.docks} == {
            "Validation",
            "History",
            "Logs",
            "Translation Memory",
            "Glossary",
        }
        assert {dock.objectName() for dock in sidebars.docks} == {
            "validation_dock",
            "history_dock",
            "logs_dock",
            "translation_memory_dock",
            "glossary_dock",
        }
        assert len(window.findChildren(QDockWidget)) == 5
        assert sidebars.validation_filter.count() == 5
        assert sidebars.validation_filter.itemData(2) == "ai_review"

        sidebars.log_view.appendPlainText("message")
        logs_dock = next(dock for dock in sidebars.docks if dock.windowTitle() == "Logs")
        clear_button = next(
            button
            for button in logs_dock.findChildren(QPushButton)
            if button.text() == "Clear logs"
        )
        clear_button.click()
        assert sidebars.log_view.toPlainText() == ""
        sidebars.copy_diagnostics_button.click()
        assert calls == ["diagnostics"]
    finally:
        window.close()
        application.processEvents()

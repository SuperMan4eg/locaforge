import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QTableView

from locaforge.presentation.application_appearance_renderer import (
    ApplicationAppearanceRenderer,
)
from locaforge.presentation.application_settings import ApplicationSettings


@pytest.mark.parametrize(
    ("theme", "style_fragment"),
    [
        ("dark", "background: #202124"),
        ("light", "background: #f7f7f7"),
    ],
)
def test_renders_theme_and_font_across_editor_widgets(
    theme: str, style_fragment: str
) -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    widgets = (QPlainTextEdit(window), QPlainTextEdit(window), QTableView(window))
    try:
        renderer = ApplicationAppearanceRenderer(window, widgets)

        renderer.render(ApplicationSettings(theme=theme, editor_font_size=15))

        assert style_fragment in window.styleSheet()
        assert all(widget.font().pointSize() == 15 for widget in widgets)
    finally:
        window.close()
        if QApplication.instance() is application:
            application.processEvents()


def test_system_theme_clears_custom_stylesheet() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    editor = QPlainTextEdit(window)
    try:
        renderer = ApplicationAppearanceRenderer(window, (editor,))
        renderer.render(ApplicationSettings(theme="dark"))

        renderer.render(ApplicationSettings(theme="system", editor_font_size=11))

        assert window.styleSheet() == ""
        assert editor.font().pointSize() == 11
    finally:
        window.close()
        if QApplication.instance() is application:
            application.processEvents()


def test_renderer_without_editor_widgets_still_applies_theme() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    try:
        renderer = ApplicationAppearanceRenderer(window, ())

        renderer.render(ApplicationSettings(theme="dark"))

        assert "background: #202124" in window.styleSheet()
    finally:
        window.close()
        if QApplication.instance() is application:
            application.processEvents()

"""Render application theme and translation-editor typography."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QWidget

from locaforge.presentation.application_settings import ApplicationSettings

_DARK_STYLE = (
    "QWidget { background: #202124; color: #e8eaed; } "
    "QLineEdit, QPlainTextEdit, QListWidget, QTableView, QComboBox, "
    "QSpinBox { background: #292a2d; color: #e8eaed; }"
)
_LIGHT_STYLE = (
    "QWidget { background: #f7f7f7; color: #202124; } "
    "QLineEdit, QPlainTextEdit, QListWidget, QTableView, QComboBox, "
    "QSpinBox { background: white; color: #202124; }"
)


class ApplicationAppearanceRenderer:
    """Apply user-selected appearance settings to the main editor surfaces."""

    def __init__(self, window: QWidget, editor_widgets: Sequence[QWidget]) -> None:
        self._window = window
        self._editor_widgets = tuple(editor_widgets)

    def render(self, settings: ApplicationSettings) -> None:
        styles = {"dark": _DARK_STYLE, "light": _LIGHT_STYLE}
        self._window.setStyleSheet(styles.get(settings.theme, ""))
        if not self._editor_widgets:
            return
        font = self._editor_widgets[0].font()
        font.setPointSize(settings.editor_font_size)
        for widget in self._editor_widgets:
            widget.setFont(font)

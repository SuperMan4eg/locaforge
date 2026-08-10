"""Project creation summary and language settings dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from locaforge.presentation.localization import tr
from locaforge.presentation.searchable_language_combo_box import SearchableLanguageComboBox


class ProjectSetupDialog(QDialog):
    """Explains import choices and confirms the new project's language pair."""

    def __init__(
        self,
        source_path: Path,
        destination_path: Path,
        source_format: str,
        mapping_description: str,
        parent: QWidget | None = None,
        default_languages: tuple[str, str] = ("en", "ru"),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create LocaForge project")
        self.setMinimumWidth(560)

        introduction = QLabel(
            "Review how the localization file will be imported. The source file is "
            "never modified; translations are stored in the portable .lfproj project.",
            self,
        )
        introduction.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Source file", self._selectable_label(str(source_path)))
        form.addRow("Detected format", self._selectable_label(source_format.upper()))
        form.addRow("Project file", self._selectable_label(str(destination_path)))
        form.addRow("Field mapping", self._selectable_label(mapping_description))

        self.source_language = SearchableLanguageComboBox(default_languages[0], self)
        self.source_language.setToolTip(
            "Language code of the text being translated; used by models, glossary, and TM"
        )
        self.target_language = SearchableLanguageComboBox(default_languages[1], self)
        self.target_language.setToolTip(
            "Language code of the resulting translation; used by models, glossary, and TM"
        )
        form.addRow("Source language", self.source_language)
        form.addRow("Target language", self.target_language)

        details = QLabel(
            "Keys identify entries and are preserved during export. Source values are sent "
            "to the translation model. Existing target values, when enabled by the field "
            "mapping, are imported as translations that still require review.",
            self,
        )
        details.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create project")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(introduction)
        layout.addLayout(form)
        layout.addWidget(details)
        layout.addWidget(buttons)

    def language_pair(self) -> tuple[str, str]:
        return (
            self.source_language.language_code() or "",
            self.target_language.language_code() or "",
        )

    def accept(self) -> None:
        source_language, target_language = self.language_pair()
        if not source_language or not target_language:
            QMessageBox.warning(
                self,
                tr("project.languages", "Project languages"),
                tr(
                    "project.enter_languages",
                    "Enter both source and target languages.",
                ),
            )
            return
        if source_language.casefold() == target_language.casefold():
            QMessageBox.warning(
                self,
                tr("project.languages", "Project languages"),
                tr(
                    "settings.languages_must_differ",
                    "Source and target languages must be different.",
                ),
            )
            return
        super().accept()

    def _selectable_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        return label

"""Project-scoped Ollama settings dialog."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from locaforge.domain.settings import ModelSettings


class OllamaSettingsDialog(QDialog):
    def __init__(
        self,
        settings: ModelSettings,
        models: Sequence[str],
        status_message: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ollama settings")

        self._model = QComboBox(self)
        self._model.setEditable(True)
        self._model.addItems(models)
        if not models and self._model.findText(settings.model) < 0:
            self._model.addItem(settings.model)
        self._model.setCurrentText(
            settings.model if settings.model in models or not models else models[0]
        )

        self._review_model = QComboBox(self)
        self._review_model.setEditable(True)
        self._review_model.addItems(models)
        review_model = settings.effective_review_model
        if not models and self._review_model.findText(review_model) < 0:
            self._review_model.addItem(review_model)
        self._review_model.setCurrentText(
            review_model
            if review_model in models or not models
            else self._model.currentText()
        )

        self._timeout = QDoubleSpinBox(self)
        self._timeout.setRange(1.0, 3600.0)
        self._timeout.setDecimals(1)
        self._timeout.setSuffix(" s")
        self._timeout.setValue(settings.timeout_seconds)

        self._batch_size = QSpinBox(self)
        self._batch_size.setRange(1, 1000)
        self._batch_size.setValue(settings.batch_size)

        self._system_prompt = QPlainTextEdit(self)
        self._system_prompt.setPlaceholderText(
            "Optional style, tone, terminology, or project-specific instructions"
        )
        self._system_prompt.setPlainText(settings.system_prompt)

        self._review_prompt = QPlainTextEdit(self)
        self._review_prompt.setPlaceholderText(
            "Criteria for meaning, terminology, completeness, and natural language"
        )
        self._review_prompt.setPlainText(settings.review_prompt)
        self._save_as_default = QCheckBox("Save as user default settings", self)

        status = QLabel(status_message, self)
        general_tab = QWidget(self)
        general_form = QFormLayout(general_tab)
        general_form.addRow("Connection", status)
        general_form.addRow("Model", self._model)
        general_form.addRow("Reviewer model", self._review_model)
        general_form.addRow("Timeout", self._timeout)
        general_form.addRow("Batch size", self._batch_size)

        prompts_tab = QWidget(self)
        prompts_form = QFormLayout(prompts_tab)
        prompts_form.addRow("Translation prompt", self._system_prompt)
        prompts_form.addRow("Reviewer prompt", self._review_prompt)

        tabs = QTabWidget(self)
        tabs.addTab(general_tab, "General")
        tabs.addTab(prompts_tab, "Prompts")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(self._save_as_default)
        layout.addWidget(buttons)
        self.resize(600, 420)

    def model_settings(self) -> ModelSettings:
        translation_model = self._model.currentText().strip()
        review_model = self._review_model.currentText().strip()
        return ModelSettings(
            model=translation_model,
            timeout_seconds=self._timeout.value(),
            batch_size=self._batch_size.value(),
            system_prompt=self._system_prompt.toPlainText(),
            review_prompt=self._review_prompt.toPlainText(),
            review_model=(review_model if review_model != translation_model else ""),
        )

    def save_as_default(self) -> bool:
        return self._save_as_default.isChecked()

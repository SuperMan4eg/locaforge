"""Project-first creation dialog."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile
from locaforge.domain.settings import REASONING_MODES, ModelSettings
from locaforge.presentation.profile_generation_worker import ProfileGenerationWorker
from locaforge.presentation.searchable_language_combo_box import SearchableLanguageComboBox


class NewProjectDialog(QDialog):
    """Collect the identity and translation context of an empty project."""

    def __init__(
        self,
        parent: QWidget | None = None,
        project: Project | None = None,
        default_languages: tuple[str, str] = ("en", "ru"),
        profile_generator: Callable[..., ProjectProfile] | None = None,
        allow_online_lookup: bool = False,
        global_model_settings: ModelSettings | None = None,
        available_models: Sequence[str] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New LocaForge project")
        self.setMinimumWidth(600)
        self._profile_generator = profile_generator
        self._profile_worker: ProfileGenerationWorker | None = None

        self.name = QLineEdit(self)
        self.name.setPlaceholderText("Project name")
        self.description = QPlainTextEdit(self)
        self.description.setPlaceholderText(
            "What is being localized? Include the setting, product, or subject matter."
        )
        self.description.setMaximumHeight(90)
        self.generate_profile = QPushButton("Generate profile with AI", self)
        self.generate_profile.setEnabled(profile_generator is not None)
        self.generate_profile.clicked.connect(self._generate_profile)
        self.online_lookup = QCheckBox("Use online search results", self)
        self.online_lookup.setEnabled(allow_online_lookup)
        self.online_lookup.setToolTip(
            "Enable online lookup in Settings > Privacy to use this option"
        )
        self.source_language = SearchableLanguageComboBox(default_languages[0], self)
        self.target_language = SearchableLanguageComboBox(default_languages[1], self)
        self.project_type = QComboBox(self)
        self.project_type.setEditable(True)
        self.project_type.addItems(("", "Game", "Application", "Website", "Documentation"))
        self.domain = QLineEdit(self)
        self.target_audience = QLineEdit(self)
        self.tone = QLineEdit(self)
        self.platform = QLineEdit(self)
        self.instructions = QPlainTextEdit(self)
        self.instructions.setPlaceholderText("Terminology, style, and other model instructions")
        self.instructions.setMaximumHeight(80)
        effective_global_settings = global_model_settings or ModelSettings()
        initial_model_settings = (
            project.model_settings
            if project is not None and project.model_settings_override_enabled
            else effective_global_settings
        )
        self.model_settings_group = QGroupBox("Model settings", self)
        self.model_settings_override = QCheckBox(
            "Override global model settings", self.model_settings_group
        )
        self.model_settings_source = QLineEdit("Global settings", self.model_settings_group)
        self.model_settings_source.setReadOnly(True)
        self.model_settings_source.setFrame(False)
        self.model_settings_source.setStyleSheet("color: palette(mid);")
        self.translation_model = self._model_combo(
            initial_model_settings.model, available_models
        )
        self.review_model = self._model_combo(
            initial_model_settings.effective_review_model, available_models
        )
        self.translation_reasoning = self._reasoning_combo(
            initial_model_settings.translation_reasoning
        )
        self.review_reasoning = self._reasoning_combo(
            initial_model_settings.review_reasoning
        )
        self.model_timeout = QDoubleSpinBox(self.model_settings_group)
        self.model_timeout.setRange(1.0, 3600.0)
        self.model_timeout.setDecimals(1)
        self.model_timeout.setSuffix(" s")
        self.model_timeout.setValue(initial_model_settings.timeout_seconds)
        self.model_batch_size = QSpinBox(self.model_settings_group)
        self.model_batch_size.setRange(1, 1000)
        self.model_batch_size.setValue(initial_model_settings.batch_size)
        self.model_keep_alive = QSpinBox(self.model_settings_group)
        self.model_keep_alive.setRange(-1, 86_400)
        self.model_keep_alive.setSpecialValueText("Keep loaded")
        self.model_keep_alive.setSuffix(" s")
        self.model_keep_alive.setValue(initial_model_settings.keep_alive_seconds)
        self.model_keep_alive.setToolTip(
            "How long Ollama keeps the model in memory; -1 keeps it loaded, 0 unloads it"
        )
        self.translation_prompt = QPlainTextEdit(self.model_settings_group)
        self.translation_prompt.setPlainText(initial_model_settings.system_prompt)
        self.translation_prompt.setMaximumHeight(80)
        self.review_prompt = QPlainTextEdit(self.model_settings_group)
        self.review_prompt.setPlainText(initial_model_settings.review_prompt)
        self.review_prompt.setMaximumHeight(80)
        self.model_settings_panel = QWidget(self.model_settings_group)
        model_form = QFormLayout(self.model_settings_panel)
        model_form.addRow("Translation model", self.translation_model)
        model_form.addRow("Reviewer model", self.review_model)
        model_form.addRow("Translation reasoning", self.translation_reasoning)
        model_form.addRow("Reviewer reasoning", self.review_reasoning)
        model_form.addRow("Timeout", self.model_timeout)
        model_form.addRow("Batch size", self.model_batch_size)
        model_form.addRow("Keep model loaded", self.model_keep_alive)
        model_form.addRow("Translation prompt", self.translation_prompt)
        model_form.addRow("Reviewer prompt", self.review_prompt)
        model_layout = QVBoxLayout(self.model_settings_group)
        model_layout.addWidget(self.model_settings_override)
        source_form = QFormLayout()
        source_form.addRow("Active source", self.model_settings_source)
        model_layout.addLayout(source_form)
        model_layout.addWidget(self.model_settings_panel)
        self.model_settings_override.toggled.connect(self._update_model_settings_visibility)

        form = QFormLayout()
        form.addRow("Name *", self.name)
        form.addRow("Description", self.description)
        form.addRow("", self.generate_profile)
        form.addRow("", self.online_lookup)
        form.addRow("Source language *", self.source_language)
        form.addRow("Target language *", self.target_language)
        form.addRow("Project type", self.project_type)
        form.addRow("Domain / genre", self.domain)
        form.addRow("Target audience", self.target_audience)
        form.addRow("Tone", self.tone)
        form.addRow("Platform", self.platform)
        form.addRow("Translation instructions", self.instructions)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create project")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        if project is not None:
            layout.addWidget(self.model_settings_group)
        layout.addWidget(self.buttons)
        if project is not None:
            self.setWindowTitle("Project settings")
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Save settings")
            self.name.setText(project.name)
            self.description.setPlainText(project.profile.description)
            self.source_language.setText(project.source_language)
            self.target_language.setText(project.target_language)
            self.project_type.setCurrentText(project.profile.project_type)
            self.domain.setText(project.profile.domain)
            self.target_audience.setText(project.profile.target_audience)
            self.tone.setText(project.profile.tone)
            self.platform.setText(project.profile.platform)
            self.instructions.setPlainText(project.profile.translation_instructions)
            self.model_settings_override.setChecked(project.model_settings_override_enabled)
            self._update_model_settings_visibility(project.model_settings_override_enabled)

    def _generate_profile(self) -> None:
        if self._profile_generator is None or self._profile_worker is not None:
            return
        name = self.name.text()
        generator = self._profile_generator
        use_online_lookup = self.online_lookup.isChecked()
        worker = ProfileGenerationWorker(
            lambda: generator(name, use_online_lookup=use_online_lookup),
            self,
        )
        worker.succeeded.connect(self._profile_generated)
        worker.failed.connect(self._profile_generation_failed)
        worker.finished.connect(worker.deleteLater)
        self._profile_worker = worker
        self._set_generation_busy(True)
        worker.start()

    def _profile_generated(self, result: object) -> None:
        self._profile_worker = None
        self._set_generation_busy(False)
        if not isinstance(result, ProjectProfile):
            QMessageBox.warning(
                self, "Generate project profile", "Model returned an invalid profile"
            )
            return
        self.description.setPlainText(result.description)
        self.project_type.setCurrentText(result.project_type)
        self.domain.setText(result.domain)
        self.target_audience.setText(result.target_audience)
        self.tone.setText(result.tone)
        self.platform.setText(result.platform)
        self.instructions.setPlainText(result.translation_instructions)

    def _profile_generation_failed(self, message: str) -> None:
        self._profile_worker = None
        self._set_generation_busy(False)
        QMessageBox.warning(self, "Generate project profile", message)

    def _set_generation_busy(self, busy: bool) -> None:
        self.generate_profile.setText(
            "Generating profile..." if busy else "Generate profile with AI"
        )
        self.generate_profile.setEnabled(not busy and self._profile_generator is not None)
        self.buttons.setEnabled(not busy)

    def _update_model_settings_visibility(self, enabled: bool) -> None:
        self.model_settings_source.setText(
            "Project settings" if enabled else "Global settings"
        )
        self.model_settings_panel.setVisible(enabled)

    def project_model_settings(self) -> ModelSettings:
        translation_model = self.translation_model.currentText().strip() or "qwen3"
        review_model = self.review_model.currentText().strip()
        return ModelSettings(
            model=translation_model,
            review_model=(review_model if review_model != translation_model else ""),
            translation_reasoning=str(self.translation_reasoning.currentData()),
            review_reasoning=str(self.review_reasoning.currentData()),
            timeout_seconds=self.model_timeout.value(),
            batch_size=self.model_batch_size.value(),
            system_prompt=self.translation_prompt.toPlainText(),
            review_prompt=self.review_prompt.toPlainText(),
            keep_alive_seconds=self.model_keep_alive.value(),
        )

    def project_values(self) -> tuple[str, str, str, ProjectProfile]:
        return (
            self.name.text().strip(),
            self.source_language.language_code() or "",
            self.target_language.language_code() or "",
            ProjectProfile(
                description=self.description.toPlainText().strip(),
                project_type=self.project_type.currentText().strip(),
                domain=self.domain.text().strip(),
                target_audience=self.target_audience.text().strip(),
                tone=self.tone.text().strip(),
                platform=self.platform.text().strip(),
                translation_instructions=self.instructions.toPlainText().strip(),
            ),
        )

    def accept(self) -> None:
        name, source_language, target_language, _ = self.project_values()
        if not name:
            QMessageBox.warning(self, "Project name", "Enter a project name.")
            return
        if not source_language or not target_language:
            QMessageBox.warning(
                self, "Project languages", "Enter both source and target languages."
            )
            return
        if source_language.casefold() == target_language.casefold():
            QMessageBox.warning(
                self,
                "Project languages",
                "Source and target languages must be different.",
            )
            return
        super().accept()

    def _model_combo(self, current: str, models: Sequence[str]) -> QComboBox:
        combo = QComboBox(self.model_settings_group)
        combo.setEditable(True)
        combo.addItems(models)
        if combo.findText(current) < 0:
            combo.addItem(current)
        combo.setCurrentText(current)
        return combo

    def _reasoning_combo(self, current: str) -> QComboBox:
        combo = QComboBox(self.model_settings_group)
        for mode in REASONING_MODES:
            combo.addItem(mode.title(), mode)
        combo.setCurrentIndex(max(0, combo.findData(current)))
        return combo

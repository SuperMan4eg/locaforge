"""Categorized application settings dialog."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from locaforge.domain.settings import ModelSettings
from locaforge.presentation.application_settings import ApplicationSettings
from locaforge.presentation.localization import LocalizationManager, PackageDiagnostic
from locaforge.presentation.searchable_language_combo_box import SearchableLanguageComboBox


class ApplicationSettingsDialog(QDialog):
    def __init__(
        self,
        settings: ApplicationSettings,
        parent: QWidget | None = None,
        test_ollama: Callable[[str], tuple[bool, str]] | None = None,
        list_models: Callable[[str], Sequence[str]] | None = None,
        pull_model: Callable[[str, str], bool] | None = None,
        open_installer: Callable[[], None] | None = None,
        localization: LocalizationManager | None = None,
        open_localization_folder: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._localization = localization
        self._open_localization_folder = open_localization_folder
        self._t = localization.translate if localization is not None else lambda key, **_params: key
        self.setWindowTitle(self._message("settings.title", "Settings"))
        self.resize(720, 480)
        self.categories = QListWidget(self)
        self.pages = QStackedWidget(self)
        self._test_ollama = test_ollama
        self._list_models = list_models
        self._pull_model = pull_model
        self._open_installer = open_installer

        self.theme = QComboBox(self)
        self.theme.addItem(self._message("settings.use_system_theme", "Use system theme"), "system")
        self.theme.addItem(self._message("settings.light", "Light"), "light")
        self.theme.addItem(self._message("settings.dark", "Dark"), "dark")
        self.theme.setCurrentIndex(max(0, self.theme.findData(settings.theme)))
        self.default_source = SearchableLanguageComboBox(settings.default_source_language, self)
        self.default_target = SearchableLanguageComboBox(settings.default_target_language, self)
        self._add_page(
            self._message("settings.general", "General"),
            (
                (self._message("settings.theme", "Theme"), self.theme),
                (
                    self._message("settings.default_source", "Default source language"),
                    self.default_source,
                ),
                (
                    self._message("settings.default_target", "Default target language"),
                    self.default_target,
                ),
            ),
        )

        self.font_size = QSpinBox(self)
        self.font_size.setRange(8, 24)
        self.font_size.setValue(settings.editor_font_size)
        self._add_page(
            self._message("settings.editor", "Editor"),
            ((self._message("settings.editor_font_size", "Editor font size"), self.font_size),),
        )

        self.autosave = QCheckBox(
            self._message("settings.enable_autosave", "Enable automatic project saving"), self
        )
        self.autosave.setChecked(settings.autosave_enabled)
        self.autosave_delay = QSpinBox(self)
        self.autosave_delay.setRange(1, 300)
        self.autosave_delay.setSuffix(self._message("settings.seconds", " seconds"))
        self.autosave_delay.setValue(settings.autosave_delay_seconds)
        self._add_page(
            self._message("settings.saving", "Saving"),
            (
                ("", self.autosave),
                (self._message("settings.autosave_delay", "Autosave delay"), self.autosave_delay),
            ),
        )

        self.export_warnings = QCheckBox(
            self._message(
                "settings.confirm_export", "Confirm export when translations or QA issues remain"
            ),
            self,
        )
        self.export_warnings.setChecked(settings.confirm_export_warnings)
        self._add_page(
            self._message("settings.import_export", "Import and export"),
            (("", self.export_warnings),),
        )

        self.online_lookup = QCheckBox(
            self._message("settings.allow_online_lookup", "Allow online project metadata lookup"),
            self,
        )
        self.online_lookup.setChecked(settings.allow_online_project_lookup)
        privacy_note = QLabel(
            self._message(
                "settings.privacy_note",
                "Source localization strings are never included in metadata searches.",
            ),
            self,
        )
        privacy_note.setWordWrap(True)
        self._add_page(
            self._message("settings.privacy", "Privacy"),
            (("", self.online_lookup), ("", privacy_note)),
        )

        self.interface_language: QComboBox | None = None
        if localization is not None:
            self.interface_language = QComboBox(self)
            for package in localization.available_languages:
                self.interface_language.addItem(package.name, package.locale)
            self.interface_language.setCurrentIndex(
                max(
                    0,
                    self.interface_language.findData(
                        localization.resolve_locale(settings.ui_locale)
                    ),
                )
            )
            self.open_localizations_button = QPushButton(
                self._message("settings.open_localizations", "Open localization folder"), self
            )
            self.open_localizations_button.clicked.connect(self._open_localizations)
            self.check_packages_button = QPushButton(
                self._message("settings.check_packages", "Check packages"), self
            )
            self.check_packages_button.clicked.connect(self._check_packages)
            self.reload_packages_button = QPushButton(
                self._message("settings.reload", "Reload"), self
            )
            self.reload_packages_button.clicked.connect(self._reload_packages)
            language_buttons = QWidget(self)
            language_layout = QHBoxLayout(language_buttons)
            language_layout.setContentsMargins(0, 0, 0, 0)
            language_layout.addWidget(self.open_localizations_button)
            language_layout.addWidget(self.check_packages_button)
            language_layout.addWidget(self.reload_packages_button)
            language_layout.addStretch()
            language_note = QLabel(
                self._message(
                    "settings.language_restart",
                    "Language changes apply after restarting the application.",
                ),
                self,
            )
            language_note.setWordWrap(True)
            self._add_page(
                self._message("settings.interface_language", "Interface language"),
                (
                    (self._message("settings.language", "Language"), self.interface_language),
                    ("", language_buttons),
                    ("", language_note),
                ),
            )

        self.ollama_server_url = QLineEdit(settings.ollama_server_url, self)
        self.ollama_status = QLabel(
            self._message("settings.connection_not_checked", "Connection not checked"), self
        )
        self.test_ollama_button = QPushButton(
            self._message("settings.test_connection", "Test connection"), self
        )
        self.test_ollama_button.clicked.connect(self._test_ollama_connection)
        self.install_ollama_button = QPushButton(
            self._message("settings.open_ollama_installer", "Open Ollama installer"), self
        )
        self.install_ollama_button.clicked.connect(self._launch_installer)
        connection_buttons = QWidget(self)
        connection_layout = QHBoxLayout(connection_buttons)
        connection_layout.setContentsMargins(0, 0, 0, 0)
        connection_layout.addWidget(self.test_ollama_button)
        connection_layout.addWidget(self.install_ollama_button)
        connection_layout.addStretch()

        self.installed_models = QListWidget(self)
        self.installed_models.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.refresh_models_button = QPushButton(
            self._message("settings.refresh_list", "Refresh list"), self
        )
        self.refresh_models_button.clicked.connect(self._refresh_models)
        models_widget = QWidget(self)
        models_layout = QVBoxLayout(models_widget)
        models_layout.setContentsMargins(0, 0, 0, 0)
        models_layout.addWidget(self.installed_models)
        models_layout.addWidget(self.refresh_models_button)

        self.model_to_download = QLineEdit(self)
        self.model_to_download.setText(settings.model_settings.model)
        self.download_model_button = QPushButton(
            self._message("settings.download_model", "Download model"), self
        )
        self.download_model_button.clicked.connect(self._download_model)
        download_widget = QWidget(self)
        download_layout = QHBoxLayout(download_widget)
        download_layout.setContentsMargins(0, 0, 0, 0)
        download_layout.addWidget(self.model_to_download)
        download_layout.addWidget(self.download_model_button)
        self.download_progress = QProgressBar(self)
        self.download_progress.setVisible(False)
        download_note = QLabel(
            self._message(
                "settings.download_note",
                "Model downloads can use several GB of disk space. Progress is reported by Ollama.",
            ),
            self,
        )
        download_note.setWordWrap(True)

        self.translation_model = self._model_combo(settings.model_settings.model)
        self.review_model = self._model_combo(settings.model_settings.effective_review_model)
        self.translation_reasoning = self._reasoning_combo(
            settings.model_settings.translation_reasoning
        )
        self.review_reasoning = self._reasoning_combo(settings.model_settings.review_reasoning)
        self.timeout = QDoubleSpinBox(self)
        self.timeout.setRange(1.0, 3600.0)
        self.timeout.setDecimals(1)
        self.timeout.setSuffix(" s")
        self.timeout.setValue(settings.model_settings.timeout_seconds)
        self.batch_size = QSpinBox(self)
        self.batch_size.setRange(1, 1000)
        self.batch_size.setValue(settings.model_settings.batch_size)
        self.translation_prompt = QPlainTextEdit(settings.model_settings.system_prompt, self)
        self.review_prompt = QPlainTextEdit(settings.model_settings.review_prompt, self)
        self._add_page(
            self._message("settings.models", "Models and Ollama"),
            (
                (self._message("settings.ollama_server", "Ollama server"), self.ollama_server_url),
                (self._message("settings.status", "Status"), self.ollama_status),
                (self._message("settings.connection", "Connection"), connection_buttons),
                (self._message("settings.installed_models", "Installed models"), models_widget),
                (self._message("settings.download", "Download"), download_widget),
                ("", self.download_progress),
                ("", download_note),
                (
                    self._message("settings.translation_model", "Translation model"),
                    self.translation_model,
                ),
                (self._message("settings.reviewer_model", "Reviewer model"), self.review_model),
                (
                    self._message("settings.translation_reasoning", "Translation reasoning"),
                    self.translation_reasoning,
                ),
                (
                    self._message("settings.reviewer_reasoning", "Reviewer reasoning"),
                    self.review_reasoning,
                ),
                (self._message("settings.timeout", "Timeout"), self.timeout),
                (self._message("settings.batch_size", "Batch size"), self.batch_size),
                (
                    self._message("settings.translation_prompt", "Translation prompt"),
                    self.translation_prompt,
                ),
                (self._message("settings.reviewer_prompt", "Reviewer prompt"), self.review_prompt),
            ),
        )

        self.categories.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.categories.setCurrentRow(0)
        content = QHBoxLayout()
        content.addWidget(self.categories, 1)
        content.addWidget(self.pages, 3)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(content)
        layout.addWidget(buttons)

    def settings(self) -> ApplicationSettings:
        return ApplicationSettings(
            ui_locale=(
                str(self.interface_language.currentData() or "en")
                if self.interface_language is not None
                else self._application_language()
            ),
            theme=str(self.theme.currentData()),
            default_source_language=self.default_source.language_code() or "en",
            default_target_language=self.default_target.language_code() or "ru",
            editor_font_size=self.font_size.value(),
            autosave_enabled=self.autosave.isChecked(),
            autosave_delay_seconds=self.autosave_delay.value(),
            confirm_export_warnings=self.export_warnings.isChecked(),
            allow_online_project_lookup=self.online_lookup.isChecked(),
            ollama_server_url=self.ollama_server_url.text().strip() or "http://127.0.0.1:11434",
            model_settings=self.model_settings(),
        )

    def model_settings(self) -> ModelSettings:
        model = self.translation_model.currentText().strip() or "qwen3"
        reviewer = self.review_model.currentText().strip()
        return ModelSettings(
            model=model,
            review_model="" if reviewer == model else reviewer,
            translation_reasoning=str(self.translation_reasoning.currentData()),
            review_reasoning=str(self.review_reasoning.currentData()),
            timeout_seconds=float(self.timeout.value()),
            batch_size=self.batch_size.value(),
            system_prompt=self.translation_prompt.toPlainText(),
            review_prompt=self.review_prompt.toPlainText(),
        )

    def set_model_pull_running(self, running: bool, message: str = "") -> None:
        self.download_progress.setVisible(running)
        self.download_progress.setRange(0, 0 if running else 1)
        self.download_model_button.setEnabled(not running)
        if message:
            self.ollama_status.setText(message)
        if not running:
            self._refresh_models()

    def _test_ollama_connection(self) -> None:
        if self._test_ollama is None:
            return
        connected, message = self._test_ollama(self.ollama_server_url.text().strip())
        self.ollama_status.setText(message)
        if connected:
            self._refresh_models()

    def _refresh_models(self) -> None:
        if self._list_models is None:
            return
        try:
            models = self._list_models(self.ollama_server_url.text().strip())
        except Exception as error:
            self.ollama_status.setText(f"Unavailable — {error}")
            return
        self.installed_models.clear()
        self.installed_models.addItems(models)
        for combo in (self.translation_model, self.review_model):
            current = combo.currentText()
            combo.clear()
            combo.addItems(models)
            combo.setCurrentText(current)
        self.ollama_status.setText(f"Connected — {len(models)} model(s) installed")

    def _download_model(self) -> None:
        model = self.model_to_download.text().strip()
        if not model or self._pull_model is None:
            return
        if self._pull_model(self.ollama_server_url.text().strip(), model):
            self.set_model_pull_running(True, f"Downloading {model}…")

    def _launch_installer(self) -> None:
        if self._open_installer is not None:
            self._open_installer()

    def accept(self) -> None:
        settings = self.settings()
        if (
            settings.default_source_language.casefold()
            == settings.default_target_language.casefold()
        ):
            QMessageBox.warning(
                self,
                self._message("settings.default_languages", "Default languages"),
                self._message(
                    "settings.languages_must_differ",
                    "Source and target languages must be different.",
                ),
            )
            return
        super().accept()

    def _message(self, key: str, english: str) -> str:
        value = self._t(key)
        return english if value == key else value

    def _application_language(self) -> str:
        return "en" if self._localization is None else self._localization.locale

    def _open_localizations(self) -> None:
        if self._open_localization_folder is not None:
            self._open_localization_folder()

    def _reload_packages(self) -> None:
        if self._localization is None:
            return
        if self.interface_language is None:
            return
        current = self.interface_language.currentData()
        self._localization.reload()
        self.interface_language.clear()
        for package in self._localization.available_languages:
            self.interface_language.addItem(package.name, package.locale)
        self.interface_language.setCurrentIndex(max(0, self.interface_language.findData(current)))
        self._show_package_diagnostics(self._localization.diagnostics)

    def _check_packages(self) -> None:
        if self._localization is None:
            return
        self._show_package_diagnostics(self._localization.validate_user_packages())

    def _show_package_diagnostics(self, diagnostics: list[PackageDiagnostic]) -> None:
        if not diagnostics:
            QMessageBox.information(
                self,
                self._message("settings.package_diagnostics", "Localization package diagnostics"),
                self._message("settings.packages_valid", "Localization packages are valid."),
            )
            return
        message = "\n".join(
            f"[{item.level}] {item.path or 'built-in'}: {item.message}" for item in diagnostics
        )
        QMessageBox.warning(
            self,
            self._message("settings.package_diagnostics", "Localization package diagnostics"),
            message,
        )

    def _add_page(self, title: str, rows: tuple[tuple[str, QWidget], ...]) -> None:
        self.categories.addItem(title)
        page = QWidget(self)
        form = QFormLayout(page)
        for label, widget in rows:
            form.addRow(label, widget)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.pages.addWidget(page)

    def _model_combo(self, current: str) -> QComboBox:
        combo = QComboBox(self)
        combo.setEditable(True)
        combo.addItem(current)
        combo.setCurrentText(current)
        return combo

    def _reasoning_combo(self, current: str) -> QComboBox:
        combo = QComboBox(self)
        for mode in ("off", "low", "medium", "high"):
            combo.addItem(mode.title(), mode)
        combo.setCurrentIndex(max(0, combo.findData(current)))
        return combo

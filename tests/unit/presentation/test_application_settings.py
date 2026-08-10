import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from typing import Any

from PySide6.QtWidgets import QApplication

from locaforge.domain.settings import ModelSettings
from locaforge.presentation.application_settings import (
    ApplicationSettings,
    ApplicationSettingsStore,
)
from locaforge.presentation.application_settings_dialog import ApplicationSettingsDialog
from locaforge.presentation.localization import LocalizationManager


class FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def value(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def setValue(self, key: str, value: object) -> None:
        self.values[key] = value


def test_application_settings_round_trip() -> None:
    backend = FakeSettings()
    store = ApplicationSettingsStore(cast_settings(backend))
    expected = ApplicationSettings(
        theme="dark",
        default_source_language="de",
        default_target_language="uk",
        editor_font_size=14,
        autosave_enabled=False,
        autosave_delay_seconds=15,
        confirm_export_warnings=False,
        allow_online_project_lookup=True,
        ollama_server_url="http://ollama.example:11434",
        model_settings=ModelSettings(model="gemma3:12b", batch_size=8),
    )

    store.save(expected)

    assert store.load() == expected
    saved = backend.values["application_settings"]
    assert isinstance(saved, dict)
    assert saved["ui_locale"] == "en"


def test_legacy_interface_language_is_loaded_as_ui_locale() -> None:
    backend = FakeSettings()
    backend.values["application_settings"] = {"interface_language": "ru"}

    assert ApplicationSettingsStore(cast_settings(backend)).load().ui_locale == "ru"


def test_settings_dialog_exposes_categories_and_values() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = ApplicationSettingsDialog(
        ApplicationSettings(theme="dark", editor_font_size=13)
    )

    assert application is not None
    assert [dialog.categories.item(index).text() for index in range(dialog.categories.count())] == [
        "General",
        "Editor",
        "Saving",
        "Import and export",
        "Privacy",
        "Models and Ollama",
    ]
    assert dialog.settings().theme == "dark"
    assert dialog.settings().editor_font_size == 13


def test_settings_dialog_resolves_regional_interface_locale(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    localization = LocalizationManager(tmp_path, "ru-RU")
    dialog = ApplicationSettingsDialog(
        ApplicationSettings(ui_locale="ru-RU"), localization=localization
    )

    assert application is not None
    assert dialog.interface_language is not None
    assert dialog.interface_language.currentData() == "ru"
    assert dialog.settings().ui_locale == "ru"


def test_settings_dialog_preserves_fractional_model_timeout() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = ApplicationSettingsDialog(
        ApplicationSettings(model_settings=ModelSettings(timeout_seconds=1.5))
    )

    assert application is not None
    assert dialog.settings().model_settings.timeout_seconds == 1.5


def test_model_download_uses_url_currently_entered_in_settings() -> None:
    application = QApplication.instance() or QApplication([])
    requests: list[tuple[str, str]] = []

    def pull_model(server_url: str, model: str) -> bool:
        requests.append((server_url, model))
        return True

    dialog = ApplicationSettingsDialog(
        ApplicationSettings(), pull_model=pull_model
    )
    dialog.ollama_server_url.setText("http://other-host:11434")
    dialog.model_to_download.setText("gemma3")

    dialog.download_model_button.click()

    assert application is not None
    assert requests == [("http://other-host:11434", "gemma3")]


def cast_settings(settings: FakeSettings) -> Any:
    return settings

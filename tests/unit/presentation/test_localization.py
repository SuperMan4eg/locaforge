import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from locaforge.presentation.localization import LocalizationManager
from locaforge.presentation.new_project_dialog import NewProjectDialog


def test_bundled_russian_package_and_english_fallback(tmp_path) -> None:
    localization = LocalizationManager(tmp_path, "ru")

    assert localization.translate("settings.title") == "Настройки"
    assert localization.translate("settings.models") == "Модели и Ollama"
    assert {package.locale for package in localization.available_languages} == {"en", "ru"}


def test_shown_dialog_is_localized_automatically(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    localization = LocalizationManager(tmp_path, "ru")
    localization.install(application)
    dialog = NewProjectDialog()
    dialog.show()
    application.processEvents()

    assert dialog.windowTitle() == "Новый проект LocaForge"
    assert dialog.generate_profile.text() == "Создать профиль с помощью AI"
    dialog.close()


def test_locale_change_resolves_os_region_and_emits_global_event(tmp_path) -> None:
    localization = LocalizationManager(tmp_path)
    changes: list[str] = []
    localization.languageChanged.connect(changes.append)

    localization.set_locale("ru_RU")

    assert localization.locale == "ru"
    assert changes == ["ru"]
    assert localization.translate("missing.key") != "missing.key"


def test_user_package_reports_unknown_missing_and_parameter_errors(tmp_path) -> None:
    (tmp_path / "test.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "locale": "test",
                    "name": "Test",
                    "fallback": "en",
                    "format_version": 1,
                },
                "messages": {
                    "settings.title": "Test",
                    "common.items_count": "Items",
                    "unknown.key": "Unknown",
                },
            }
        ),
        encoding="utf-8",
    )

    localization = LocalizationManager(tmp_path)

    assert any("unknown keys" in item.message for item in localization.diagnostics)
    assert any("missing strings" in item.message for item in localization.diagnostics)
    assert any("different parameters" in item.message for item in localization.diagnostics)


def test_valid_user_package_is_loaded_and_uses_english_fallback(tmp_path) -> None:
    (tmp_path / "pirate.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "locale": "pirate",
                    "name": "Pirate",
                    "fallback": "en",
                    "format_version": 1,
                },
                "messages": {"settings.title": "Ship settings"},
            }
        ),
        encoding="utf-8",
    )

    localization = LocalizationManager(tmp_path, "pirate")

    assert localization.translate("settings.title") == "Ship settings"
    assert localization.translate("settings.models") == "Models and Ollama"

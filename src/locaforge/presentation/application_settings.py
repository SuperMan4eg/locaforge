"""User-scoped desktop application preferences."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Self

from PySide6.QtCore import QLocale

from locaforge.domain.settings import ModelSettings


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    ui_locale: str = "en"
    theme: str = "system"
    default_source_language: str = "en"
    default_target_language: str = "ru"
    editor_font_size: int = 10
    autosave_enabled: bool = True
    autosave_delay_seconds: int = 2
    confirm_export_warnings: bool = True
    allow_online_project_lookup: bool = False
    ollama_server_url: str = "http://127.0.0.1:11434"
    model_settings: ModelSettings = ModelSettings()

    @classmethod
    def from_mapping(cls, value: object) -> Self:
        if not isinstance(value, dict):
            return cls()
        defaults = cls()
        raw_ui_locale = value.get("ui_locale", value.get("interface_language"))
        raw_theme = value.get("theme")
        theme = raw_theme if isinstance(raw_theme, str) else defaults.theme
        model_settings = value.get("model_settings")
        # The separate key was used before model preferences were centralized.
        # Read it here as a one-way compatibility migration on the next save.
        if not isinstance(model_settings, dict):
            model_settings = value.get("model_settings_profile", {})
        return cls(
            ui_locale=raw_ui_locale if isinstance(raw_ui_locale, str) else defaults.ui_locale,
            theme=theme if theme in {"system", "light", "dark"} else defaults.theme,
            default_source_language=str(
                value.get("default_source_language", defaults.default_source_language)
            ),
            default_target_language=str(
                value.get("default_target_language", defaults.default_target_language)
            ),
            editor_font_size=max(
                8, min(24, int(value.get("editor_font_size", defaults.editor_font_size)))
            ),
            autosave_enabled=bool(value.get("autosave_enabled", defaults.autosave_enabled)),
            autosave_delay_seconds=max(
                1,
                min(300, int(value.get("autosave_delay_seconds", defaults.autosave_delay_seconds))),
            ),
            confirm_export_warnings=bool(
                value.get("confirm_export_warnings", defaults.confirm_export_warnings)
            ),
            allow_online_project_lookup=bool(
                value.get("allow_online_project_lookup", defaults.allow_online_project_lookup)
            ),
            ollama_server_url=(
                value.get("ollama_server_url", defaults.ollama_server_url).strip()
                if isinstance(value.get("ollama_server_url"), str)
                and value["ollama_server_url"].strip()
                else defaults.ollama_server_url
            ),
            model_settings=ModelSettings.from_mapping(model_settings),
        )


class ApplicationSettingsStore:
    _KEY = "application_settings"

    def __init__(self, settings: Any) -> None:
        self._settings = settings

    def load(self) -> ApplicationSettings:
        value = self._settings.value(self._KEY, {})
        if not isinstance(value, dict):
            value = {}
        if "ui_locale" not in value and "interface_language" not in value:
            # On the first launch use the OS language.  LocalizationManager
            # resolves unavailable regional/language packages to English.
            value = {**value, "ui_locale": QLocale.system().name().replace("_", "-")}
            self._settings.setValue(self._KEY, value)
        if "model_settings" not in value:
            legacy = self._settings.value("model_settings_profile", {})
            if isinstance(legacy, dict):
                value = {**value, "model_settings": legacy}
        return ApplicationSettings.from_mapping(value)

    def save(self, settings: ApplicationSettings) -> None:
        self._settings.setValue(self._KEY, asdict(settings))

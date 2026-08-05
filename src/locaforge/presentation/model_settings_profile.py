"""User-scoped default model settings."""

from PySide6.QtCore import QSettings

from locaforge.domain.settings import ModelSettings


class ModelSettingsProfileStore:
    _KEY = "model_settings_profile"

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def load(self) -> ModelSettings:
        value = self._settings.value(self._KEY, {})
        return ModelSettings.from_mapping(value) if isinstance(value, dict) else ModelSettings()

    def save(self, model_settings: ModelSettings) -> None:
        self._settings.setValue(self._KEY, model_settings.to_dict())

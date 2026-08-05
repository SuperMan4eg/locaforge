from PySide6.QtCore import QSettings

from locaforge.domain.settings import ModelSettings
from locaforge.presentation.model_settings_profile import ModelSettingsProfileStore


def test_model_settings_profile_round_trips() -> None:
    settings = QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, "test", "model-profile"
    )
    settings.clear()
    store = ModelSettingsProfileStore(settings)
    profile = ModelSettings(model="qwen3:8b", batch_size=8)

    store.save(profile)

    assert store.load() == profile

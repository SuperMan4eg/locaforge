import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings

from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.presentation.json_import_profiles import (
    JsonImportProfile,
    JsonImportProfileStore,
)


def test_profile_store_saves_and_replaces_named_mapping() -> None:
    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "test", "profiles")
    settings.clear()
    store = JsonImportProfileStore(settings)
    store.save(JsonImportProfile("Chinese", JsonFieldMapping("ch", "en", "key")))
    store.save(JsonImportProfile("Chinese", JsonFieldMapping("tc", "en", "keyID", False)))

    assert store.list_profiles() == (
        JsonImportProfile("Chinese", JsonFieldMapping("tc", "en", "keyID", False)),
    )

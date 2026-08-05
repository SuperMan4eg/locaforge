"""Persisted JSON field-mapping profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass

from PySide6.QtCore import QSettings

from locaforge.application.ports.json_format import JsonFieldMapping


@dataclass(frozen=True, slots=True)
class JsonImportProfile:
    name: str
    mapping: JsonFieldMapping


class JsonImportProfileStore:
    _SETTINGS_KEY = "json_import_profiles"

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def list_profiles(self) -> tuple[JsonImportProfile, ...]:
        raw_value = self._settings.value(self._SETTINGS_KEY, "[]")
        try:
            items = json.loads(str(raw_value))
        except json.JSONDecodeError:
            return ()
        if not isinstance(items, list):
            return ()
        profiles: list[JsonImportProfile] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            source_field = item.get("source_field")
            target_field = item.get("target_field")
            key_field = item.get("key_field")
            if not isinstance(name, str) or not isinstance(source_field, str) or not isinstance(
                target_field, str
            ):
                continue
            profiles.append(
                JsonImportProfile(
                    name,
                    JsonFieldMapping(
                        source_field,
                        target_field,
                        key_field if isinstance(key_field, str) else None,
                        bool(item.get("import_existing_translations", True)),
                    ),
                )
            )
        return tuple(sorted(profiles, key=lambda profile: profile.name.casefold()))

    def save(self, profile: JsonImportProfile) -> None:
        profiles = [item for item in self.list_profiles() if item.name != profile.name]
        profiles.append(profile)
        serialized = [
            {
                "name": item.name,
                "source_field": item.mapping.source_field,
                "target_field": item.mapping.target_field,
                "key_field": item.mapping.key_field,
                "import_existing_translations": item.mapping.import_existing_translations,
            }
            for item in profiles
        ]
        self._settings.setValue(self._SETTINGS_KEY, json.dumps(serialized, ensure_ascii=False))

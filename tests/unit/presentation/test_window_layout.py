from __future__ import annotations

from PySide6.QtCore import QByteArray

from locaforge.presentation.window_layout import WindowLayoutStore


class FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def value(self, key: str) -> object | None:
        return self.values.get(key)

    def setValue(self, key: str, value: object) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)


def test_window_layout_store_round_trips_geometry_and_state() -> None:
    store = WindowLayoutStore(FakeSettings())
    geometry = QByteArray(b"geometry")
    state = QByteArray(b"state")

    store.save(geometry, state)

    assert store.load() == (geometry, state)


def test_window_layout_store_ignores_incomplete_or_invalid_saved_data() -> None:
    settings = FakeSettings()
    settings.setValue("window/geometry", QByteArray(b"geometry"))
    settings.setValue("window/state", "invalid")
    store = WindowLayoutStore(settings)

    assert store.load() is None

    store.clear()
    assert settings.values == {}

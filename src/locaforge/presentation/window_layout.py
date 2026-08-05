"""Persistence for the desktop window geometry and dock layout."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QByteArray


class WindowLayoutStore:
    _GEOMETRY_KEY = "window/geometry"
    _STATE_KEY = "window/state"

    def __init__(self, settings: Any) -> None:
        self._settings = settings

    def load(self) -> tuple[QByteArray, QByteArray] | None:
        geometry = self._settings.value(self._GEOMETRY_KEY)
        state = self._settings.value(self._STATE_KEY)
        if not isinstance(geometry, QByteArray) or not isinstance(state, QByteArray):
            return None
        return geometry, state

    def save(self, geometry: QByteArray, state: QByteArray) -> None:
        self._settings.setValue(self._GEOMETRY_KEY, geometry)
        self._settings.setValue(self._STATE_KEY, state)

    def clear(self) -> None:
        self._settings.remove(self._GEOMETRY_KEY)
        self._settings.remove(self._STATE_KEY)

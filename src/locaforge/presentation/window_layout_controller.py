"""Window geometry and dock-layout lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QByteArray

from locaforge.presentation.window_layout import WindowLayoutStore


class WindowLayoutController:
    """Restores, persists, and resets one main-window layout."""

    def __init__(
        self,
        store: WindowLayoutStore,
        default_geometry: QByteArray,
        default_state: QByteArray,
        save_geometry: Callable[[], QByteArray],
        save_state: Callable[[], QByteArray],
        restore_geometry: Callable[[QByteArray], object],
        restore_state: Callable[[QByteArray], object],
        show_status: Callable[[str, int], None],
    ) -> None:
        self._store = store
        self._default_geometry = default_geometry
        self._default_state = default_state
        self._save_geometry = save_geometry
        self._save_state = save_state
        self._restore_geometry = restore_geometry
        self._restore_state = restore_state
        self._show_status = show_status

    def restore(self) -> None:
        saved_layout = self._store.load()
        if saved_layout is None:
            return
        geometry, state = saved_layout
        self._restore_geometry(geometry)
        self._restore_state(state)

    def persist(self) -> None:
        self._store.save(self._save_geometry(), self._save_state())

    def reset(self) -> None:
        self._store.clear()
        self._restore_geometry(self._default_geometry)
        self._restore_state(self._default_state)
        self._show_status("Window layout reset", 3000)

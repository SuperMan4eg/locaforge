from typing import Any, cast

from PySide6.QtCore import QByteArray

from locaforge.presentation.window_layout_controller import WindowLayoutController


class StoreStub:
    def __init__(self, loaded: tuple[QByteArray, QByteArray] | None = None) -> None:
        self.loaded = loaded
        self.saved: list[tuple[QByteArray, QByteArray]] = []
        self.clear_calls = 0

    def load(self) -> tuple[QByteArray, QByteArray] | None:
        return self.loaded

    def save(self, geometry: QByteArray, state: QByteArray) -> None:
        self.saved.append((geometry, state))

    def clear(self) -> None:
        self.clear_calls += 1


def make_controller(store: StoreStub):
    restored_geometry: list[QByteArray] = []
    restored_state: list[QByteArray] = []
    statuses: list[tuple[str, int]] = []
    controller = WindowLayoutController(
        cast(Any, store),
        QByteArray(b"default-geometry"),
        QByteArray(b"default-state"),
        save_geometry=lambda: QByteArray(b"current-geometry"),
        save_state=lambda: QByteArray(b"current-state"),
        restore_geometry=lambda value: restored_geometry.append(value),
        restore_state=lambda value: restored_state.append(value),
        show_status=lambda message, timeout: statuses.append((message, timeout)),
    )
    return controller, restored_geometry, restored_state, statuses


def test_restore_applies_saved_geometry_and_state() -> None:
    store = StoreStub((QByteArray(b"saved-geometry"), QByteArray(b"saved-state")))
    controller, geometries, states, statuses = make_controller(store)

    controller.restore()

    assert geometries == [QByteArray(b"saved-geometry")]
    assert states == [QByteArray(b"saved-state")]
    assert statuses == []


def test_restore_without_snapshot_does_nothing() -> None:
    store = StoreStub()
    controller, geometries, states, statuses = make_controller(store)

    controller.restore()

    assert geometries == states == []
    assert statuses == []


def test_persist_captures_current_geometry_and_state() -> None:
    store = StoreStub()
    controller, _, _, _ = make_controller(store)

    controller.persist()

    assert store.saved == [
        (QByteArray(b"current-geometry"), QByteArray(b"current-state"))
    ]


def test_reset_clears_store_and_restores_defaults() -> None:
    store = StoreStub()
    controller, geometries, states, statuses = make_controller(store)

    controller.reset()

    assert store.clear_calls == 1
    assert geometries == [QByteArray(b"default-geometry")]
    assert states == [QByteArray(b"default-state")]
    assert statuses == [("Window layout reset", 3000)]

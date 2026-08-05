from __future__ import annotations

from pathlib import Path

import pytest

from locaforge.presentation.recent_projects import RecentProjectsStore


class FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def value(self, key: str) -> object | None:
        return self.values.get(key)

    def setValue(self, key: str, value: object) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)


def test_recent_projects_store_orders_deduplicates_and_limits_paths(tmp_path: Path) -> None:
    store = RecentProjectsStore(FakeSettings(), limit=2)
    first = tmp_path / "first.lfproj"
    second = tmp_path / "second.lfproj"
    third = tmp_path / "third.lfproj"

    store.add(first)
    store.add(second)
    store.add(first)
    store.add(third)

    assert store.list_paths() == (third.resolve(), first.resolve())


def test_recent_projects_store_removes_and_clears_paths(tmp_path: Path) -> None:
    settings = FakeSettings()
    store = RecentProjectsStore(settings)
    first = tmp_path / "first.lfproj"
    second = tmp_path / "second.lfproj"
    store.add(first)
    store.add(second)

    store.remove(first)
    assert store.list_paths() == (second.resolve(),)
    store.clear()
    assert store.list_paths() == ()


def test_recent_projects_store_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        RecentProjectsStore(FakeSettings(), limit=0)

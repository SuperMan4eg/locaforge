"""Persistence for recently opened project containers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class RecentProjectsStore:
    _KEY = "recent_projects"

    def __init__(self, settings: Any, limit: int = 10) -> None:
        if limit < 1:
            raise ValueError("Recent project limit must be positive")
        self._settings = settings
        self._limit = limit

    def list_paths(self) -> tuple[Path, ...]:
        value = self._settings.value(self._KEY)
        values: tuple[str, ...]
        if isinstance(value, str):
            values = (value,)
        elif isinstance(value, list):
            values = tuple(item for item in value if isinstance(item, str))
        else:
            values = ()
        return tuple(Path(value) for value in values)

    def add(self, path: Path) -> None:
        normalized_path = path.resolve(strict=False)
        paths = [
            existing_path
            for existing_path in self.list_paths()
            if existing_path.resolve(strict=False) != normalized_path
        ]
        self._settings.setValue(
            self._KEY,
            [str(item) for item in (normalized_path, *paths[: self._limit - 1])],
        )

    def remove(self, path: Path) -> None:
        normalized_path = path.resolve(strict=False)
        self._settings.setValue(
            self._KEY,
            [
                str(existing_path)
                for existing_path in self.list_paths()
                if existing_path.resolve(strict=False) != normalized_path
            ],
        )

    def clear(self) -> None:
        self._settings.remove(self._KEY)

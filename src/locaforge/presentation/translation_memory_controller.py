"""Asynchronous translation-memory lookup orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPushButton

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.translation_memory import TranslationMemoryMatch
from locaforge.presentation.translation_memory_worker import TranslationMemoryWorker

logger = logging.getLogger(__name__)


class TranslationMemoryController(QObject):
    """Owns debouncing, caching, and stale-result rejection for TM lookups."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        suggestions: QListWidget,
        apply_button: QPushButton,
        can_apply: Callable[[], bool],
        apply_suggestion: Callable[[], None],
        parent: QObject | None = None,
        debounce_ms: int = 120,
        cache_size: int = 64,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._suggestions = suggestions
        self._apply_button = apply_button
        self._can_apply = can_apply
        self._apply_suggestion = apply_suggestion
        self._cache_size = cache_size
        self._cache: dict[str, tuple[TranslationMemoryMatch, ...]] = {}
        self._current_entry_id: str | None = None
        self._pending_entry_id: str | None = None
        self._request_id = 0
        self._worker: TranslationMemoryWorker | None = None
        self._suggestion: str | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._start_pending_lookup)
        suggestions.currentItemChanged.connect(self._select_suggestion)
        suggestions.itemActivated.connect(self._activate_suggestion)
        apply_button.clicked.connect(apply_suggestion)

    @property
    def suggestion(self) -> str | None:
        return self._suggestion

    def refresh(self, entry_id: str) -> None:
        self._suggestions.clear()
        self._suggestion = None
        self._apply_button.setEnabled(False)
        self._current_entry_id = entry_id
        self._request_id += 1
        cached_matches = self._cache.get(entry_id)
        if cached_matches is not None:
            self._display_matches(cached_matches)
            return
        self._pending_entry_id = entry_id
        self._timer.start()

    def clear(self) -> None:
        self._suggestion = None
        self._current_entry_id = None
        self._pending_entry_id = None
        self._timer.stop()
        self._request_id += 1
        self._suggestions.clear()
        self._apply_button.setEnabled(False)

    def invalidate(self) -> None:
        self._cache.clear()
        self._pending_entry_id = None
        self._timer.stop()
        self._request_id += 1

    def reload_current(self) -> None:
        """Discard cached matches and reload the currently selected entry."""
        entry_id = self._current_entry_id
        self.invalidate()
        if entry_id is not None:
            self.refresh(entry_id)

    def _start_pending_lookup(self) -> None:
        if self._worker is not None or self._pending_entry_id is None:
            return
        entry_id = self._pending_entry_id
        self._pending_entry_id = None
        request_id = self._request_id
        worker = TranslationMemoryWorker(
            request_id,
            lambda: self._workspace.translation_memory_matches(entry_id),
            self,
        )
        worker.succeeded.connect(
            lambda received_id, matches: self._matches_loaded(
                entry_id, received_id, matches
            )
        )
        worker.failed.connect(self._lookup_failed)
        worker.finished.connect(self._lookup_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _matches_loaded(
        self, entry_id: str, request_id: int, matches_object: object
    ) -> None:
        if request_id != self._request_id or entry_id != self._current_entry_id:
            return
        if not isinstance(matches_object, tuple):
            return
        matches = tuple(
            match for match in matches_object if isinstance(match, TranslationMemoryMatch)
        )
        if len(self._cache) >= self._cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[entry_id] = matches
        self._display_matches(matches)

    def _display_matches(self, matches: tuple[TranslationMemoryMatch, ...]) -> None:
        for match in matches:
            context = f" [{match.record.context}]" if match.record.context else ""
            item = QListWidgetItem(
                f"{match.score:.0%} | {match.record.source}{context}\n"
                f"{match.record.translation}"
            )
            item.setData(Qt.ItemDataRole.UserRole, match.record.translation)
            self._suggestions.addItem(item)
        if self._suggestions.count():
            self._suggestions.setCurrentRow(0)
        else:
            self._suggestion = None
            self._apply_button.setEnabled(False)

    def _lookup_failed(self, request_id: int, message: str) -> None:
        if request_id == self._request_id:
            logger.warning("Translation memory lookup failed: %s", message)

    def _lookup_finished(self) -> None:
        self._worker = None
        if self._pending_entry_id is not None:
            self._start_pending_lookup()

    def _select_suggestion(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        translation = current.data(Qt.ItemDataRole.UserRole) if current else None
        self._suggestion = translation if isinstance(translation, str) else None
        self._apply_button.setEnabled(
            self._suggestion is not None and self._can_apply()
        )

    def _activate_suggestion(self, item: QListWidgetItem) -> None:
        self._suggestions.setCurrentItem(item)
        self._apply_suggestion()

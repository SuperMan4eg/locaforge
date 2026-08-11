"""Background-operation busy and progress presentation orchestration."""

from __future__ import annotations

from collections.abc import Callable


class OperationProgressController:
    """Coordinates shared progress and cancel controls for background work."""

    def __init__(
        self,
        set_busy_state: Callable[[bool], None],
        cancel_autosave: Callable[[], None],
        set_progress_visible: Callable[[bool], None],
        set_cancel_visible: Callable[[bool], None],
        set_cancel_enabled: Callable[[bool], None],
        set_progress_range: Callable[[int, int], None],
        set_progress_value: Callable[[int], None],
        refresh_project: Callable[[], None],
        show_status: Callable[[str], None],
    ) -> None:
        self._set_busy_state = set_busy_state
        self._cancel_autosave = cancel_autosave
        self._set_progress_visible = set_progress_visible
        self._set_cancel_visible = set_cancel_visible
        self._set_cancel_enabled = set_cancel_enabled
        self._set_progress_range = set_progress_range
        self._set_progress_value = set_progress_value
        self._refresh_project = refresh_project
        self._show_status = show_status

    def set_busy(self, busy: bool, *, refresh: bool = True) -> None:
        self._set_busy_state(busy)
        if busy:
            self._cancel_autosave()
        self._set_progress_visible(busy)
        self._set_cancel_visible(busy)
        self._set_cancel_enabled(busy)
        if not busy:
            self._set_progress_value(0)
        if refresh:
            self._refresh_project()

    def translation_progress(self, completed: int, total: int) -> None:
        self._update_progress(completed, total, "Translating")

    def review_progress(self, completed: int, total: int) -> None:
        self._update_progress(completed, total, "Reviewing")

    def prepare_model_pull(self) -> None:
        self._set_cancel_enabled(False)
        self._set_progress_range(0, 0)

    def _update_progress(self, completed: int, total: int, operation: str) -> None:
        self._set_progress_range(0, max(total, 1))
        self._set_progress_value(completed)
        self._show_status(f"{operation} {completed} of {total}")

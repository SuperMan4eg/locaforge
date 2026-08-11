"""Bulk translation, review, approval, and locking orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from locaforge.application.project_workspace import ProjectWorkspace

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


class BulkEntryOperationsController:
    """Coordinates common operations over selected or eligible entries."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        selected_entry_ids: Callable[[], Sequence[str]],
        current_entry_id: Callable[[], str | None],
        current_entry_locked: Callable[[], bool],
        is_busy: Callable[[], bool],
        start_translation: Callable[[tuple[str, ...]], object],
        start_review: Callable[[tuple[str, ...]], object],
        run_action: ActionRunner,
        show_information: Callable[[str, str], None],
    ) -> None:
        self._workspace = workspace
        self._selected_entry_ids = selected_entry_ids
        self._current_entry_id = current_entry_id
        self._current_entry_locked = current_entry_locked
        self._is_busy = is_busy
        self._start_translation = start_translation
        self._start_review = start_review
        self._run_action = run_action
        self._show_information = show_information

    def translate_selected(self) -> None:
        if not self._can_start():
            return
        entry_ids = tuple(self._selected_entry_ids())
        if not entry_ids:
            self._show_information("Batch translation", "Select one or more rows")
            return
        self._start_translation(tuple(entry_ids))

    def translate_all_untranslated(self) -> None:
        if not self._can_start():
            return
        entry_ids = self._workspace.untranslated_entry_ids()
        if not entry_ids:
            self._show_information(
                "Batch translation", "There are no untranslated entries to translate."
            )
            return
        self._start_translation(entry_ids)

    def review_selected(self) -> None:
        if not self._can_start():
            return
        entry_ids = tuple(self._selected_entry_ids())
        if not entry_ids:
            self._show_information("AI review", "Select one or more rows")
            return
        self._start_review(tuple(entry_ids))

    def review_all(self) -> None:
        if not self._can_start():
            return
        entry_ids = self._workspace.reviewable_entry_ids()
        if not entry_ids:
            self._show_information(
                "AI review", "There are no unlocked Needs review entries"
            )
            return
        self._start_review(entry_ids)

    def retranslate_current_entry(self) -> None:
        entry_id = self._current_entry_id()
        if entry_id is not None and not self._current_entry_locked():
            self._start_translation((entry_id,))

    def approve_selected(self) -> None:
        self._apply_bulk_approval(True)

    def reopen_selected(self) -> None:
        self._apply_bulk_approval(False)

    def lock_selected(self) -> None:
        self._apply_bulk_lock(True)

    def unlock_selected(self) -> None:
        self._apply_bulk_lock(False)

    def _apply_bulk_approval(self, approved: bool) -> None:
        entry_ids = tuple(self._selected_entry_ids())
        if not entry_ids:
            self._show_information("Review", "Select one or more rows")
            return
        self._run_action(
            lambda: self._workspace.set_entries_approval(entry_ids, approved),
            "Selected translations approved"
            if approved
            else "Selected translations reopened for review",
        )

    def _apply_bulk_lock(self, locked: bool) -> None:
        entry_ids = tuple(self._selected_entry_ids())
        if not entry_ids:
            self._show_information("Review", "Select one or more rows")
            return
        self._run_action(
            lambda: self._workspace.set_entries_locked(entry_ids, locked),
            "Selected translations locked" if locked else "Selected translations unlocked",
        )

    def _can_start(self) -> bool:
        return self._workspace.has_project and not self._is_busy()

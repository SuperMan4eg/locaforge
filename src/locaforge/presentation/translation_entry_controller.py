"""Operations on the currently selected translation entry."""

from __future__ import annotations

from collections.abc import Callable

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import EntryStatus

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


class TranslationEntryController:
    """Coordinates editing actions for the current translation entry."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        current_entry_id: Callable[[], str | None],
        current_entry_locked: Callable[[], bool],
        is_busy: Callable[[], bool],
        source_text: Callable[[], str],
        translation_text: Callable[[], str],
        set_translation_text: Callable[[str], None],
        set_lock_checked: Callable[[bool], None],
        run_action: ActionRunner,
        show_status: Callable[[str, int], None],
        show_warning: Callable[[str, str], None],
        confirm_matching_apply: Callable[[int], bool],
    ) -> None:
        self._workspace = workspace
        self._current_entry_id = current_entry_id
        self._current_entry_locked = current_entry_locked
        self._is_busy = is_busy
        self._source_text = source_text
        self._translation_text = translation_text
        self._set_translation_text = set_translation_text
        self._set_lock_checked = set_lock_checked
        self._run_action = run_action
        self._show_status = show_status
        self._show_warning = show_warning
        self._confirm_matching_apply = confirm_matching_apply

    def copy_source_to_translation(self) -> None:
        if (
            self._current_entry_id() is None
            or self._current_entry_locked()
            or self._is_busy()
        ):
            return
        self._set_translation_text(self._source_text())
        self._show_status("Source copied to translation editor", 3000)

    def select_translation_candidate(self, candidate: str) -> None:
        entry_id = self._current_entry_id()
        if entry_id is None or self._current_entry_locked() or self._is_busy():
            return
        label = "model" if candidate == "model" else "reviewer"
        self._run_action(
            lambda: self._workspace.select_translation_candidate(entry_id, candidate),
            f"{label.capitalize()} translation selected",
        )

    def undo_last_translation(self) -> None:
        if self._workspace.has_project and not self._is_busy():
            self._run_action(
                self._workspace.undo_last_translation,
                "Last operation undone",
            )

    def redo_last_translation(self) -> None:
        if self._workspace.has_project and not self._is_busy():
            self._run_action(
                self._workspace.redo_last_translation,
                "Last operation redone",
            )

    def apply_translation_to_matches(self) -> None:
        entry_id = self._current_entry_id()
        if entry_id is None:
            return
        translation = self._translation_text()
        if not translation.strip():
            self._show_warning(
                "Apply to matching source",
                "Enter a non-empty translation before applying it to matching entries.",
            )
            return
        current_entry = self._workspace.project.get_entry(entry_id)
        matching_count = sum(
            not entry.locked
            and entry.source == current_entry.source
            and entry.context == current_entry.context
            for entry in self._workspace.project.entries
        )
        if matching_count < 2 or not self._confirm_matching_apply(matching_count):
            return
        self._run_action(
            lambda: self._workspace.apply_translation_to_matches(entry_id, translation),
            f"Translation applied to {matching_count} entries",
        )

    def toggle_entry_approval(self) -> None:
        entry_id = self._current_entry_id()
        if entry_id is None:
            return
        entry = self._workspace.project.get_entry(entry_id)
        approved = entry.status is not EntryStatus.APPROVED
        self._run_action(
            lambda: self._workspace.set_entry_approval(entry.id, approved),
            "Translation approved" if approved else "Translation reopened for review",
        )

    def set_entry_locked(self, locked: bool) -> None:
        entry_id = self._current_entry_id()
        if entry_id is None:
            self._set_lock_checked(False)
            return
        self._run_action(
            lambda: self._workspace.set_entry_locked(entry_id, locked),
            "Translation locked" if locked else "Translation unlocked",
        )

"""Fast presentation update boundary for one-entry mutations."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import TranslationEntry

logger = logging.getLogger(__name__)
type EntryAction = Callable[[], TranslationEntry]


class EntryActionRunner:
    """Run one entry mutation without rebuilding the complete project UI."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        is_busy: Callable[[], bool],
        current_entry_id: Callable[[], str | None],
        invalidate_memory: Callable[[], None],
        update_entry: Callable[[TranslationEntry], None],
        update_filter_entries: Callable[[Sequence[TranslationEntry]], None],
        update_project_title: Callable[[], None],
        schedule_summary_refresh: Callable[[], None],
        refresh_memory: Callable[[str], None],
        sync_autosave: Callable[[], None],
        show_status: Callable[[str, int], None],
        show_error: Callable[[str], None],
    ) -> None:
        self._workspace = workspace
        self._is_busy = is_busy
        self._current_entry_id = current_entry_id
        self._invalidate_memory = invalidate_memory
        self._update_entry = update_entry
        self._update_filter_entries = update_filter_entries
        self._update_project_title = update_project_title
        self._schedule_summary_refresh = schedule_summary_refresh
        self._refresh_memory = refresh_memory
        self._sync_autosave = sync_autosave
        self._show_status = show_status
        self._show_error = show_error

    def run(self, action: EntryAction, success_message: str) -> bool:
        if self._is_busy():
            return False
        try:
            entry = action()
        except Exception as error:
            logger.exception("Entry action failed")
            self._show_error(str(error))
            return False
        self._invalidate_memory()
        self._update_entry(entry)
        entries = self._workspace.project.entries if self._workspace.has_project else ()
        self._update_filter_entries(entries)
        self._update_project_title()
        self._schedule_summary_refresh()
        if self._current_entry_id() == entry.id:
            self._refresh_memory(entry.id)
        self._sync_autosave()
        self._show_status(success_message, 5000)
        return True

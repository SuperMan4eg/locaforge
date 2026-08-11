"""Consistent execution boundary for project-level UI actions."""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

type ProjectAction = Callable[[], object]


class ProjectActionRunner:
    """Run a project mutation and apply its presentation side effects."""

    def __init__(
        self,
        is_busy: Callable[[], bool],
        refresh_project: Callable[[], None],
        sync_autosave: Callable[[], None],
        show_status: Callable[[str, int], None],
        show_error: Callable[[str], None],
    ) -> None:
        self._is_busy = is_busy
        self._refresh_project = refresh_project
        self._sync_autosave = sync_autosave
        self._show_status = show_status
        self._show_error = show_error

    def run(self, action: ProjectAction, success_message: str) -> bool:
        if self._is_busy():
            return False
        try:
            action()
        except Exception as error:
            logger.exception("Project action failed")
            self._show_error(str(error))
            return False
        self._refresh_project()
        self._sync_autosave()
        self._show_status(success_message, 5000)
        return True

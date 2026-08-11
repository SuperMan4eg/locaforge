"""Render project availability state across actions and widgets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtGui import QAction

from locaforge.presentation.edit_actions import EditActions


class EnableTarget(Protocol):
    def setEnabled(self, enabled: bool) -> None: ...


@dataclass(frozen=True, slots=True)
class ProjectActionState:
    has_project: bool
    busy: bool
    has_selected_documents: bool
    source_format: str | None
    undo_label: str | None = None
    can_undo: bool = False
    redo_label: str | None = None
    can_redo: bool = False


class ProjectActionStateRenderer:
    """Apply one project-state snapshot to all command surfaces."""

    def __init__(
        self,
        *,
        edit_actions: EditActions,
        idle_targets: tuple[EnableTarget, ...],
        project_targets: tuple[EnableTarget, ...],
        selected_document_targets: tuple[EnableTarget, ...],
        format_export_targets: Mapping[str, QAction],
        reset_disabled_targets: tuple[EnableTarget, ...],
        set_issues_enabled: Callable[[bool], None],
        set_glossary_enabled: Callable[[bool], None],
    ) -> None:
        self._edit_actions = edit_actions
        self._idle_targets = idle_targets
        self._project_targets = project_targets
        self._selected_document_targets = selected_document_targets
        self._format_export_targets = format_export_targets
        self._reset_disabled_targets = reset_disabled_targets
        self._set_issues_enabled = set_issues_enabled
        self._set_glossary_enabled = set_glossary_enabled

    def render(self, state: ProjectActionState) -> None:
        idle_enabled = not state.busy
        project_enabled = state.has_project and idle_enabled
        selected_enabled = project_enabled and state.has_selected_documents
        for target in self._idle_targets:
            target.setEnabled(idle_enabled)
        for target in self._project_targets:
            target.setEnabled(project_enabled)
        for target in self._selected_document_targets:
            target.setEnabled(selected_enabled)
        for source_format, action in self._format_export_targets.items():
            action.setEnabled(project_enabled and state.source_format == source_format)
        for target in self._reset_disabled_targets:
            target.setEnabled(False)

        self._edit_actions.undo.setText(
            f"Undo {state.undo_label}"
            if state.undo_label
            else "Undo last operation"
        )
        self._edit_actions.undo.setEnabled(
            project_enabled and state.undo_label is not None and state.can_undo
        )
        self._edit_actions.redo.setText(
            f"Redo {state.redo_label}"
            if state.redo_label
            else "Redo last operation"
        )
        self._edit_actions.redo.setEnabled(
            project_enabled and state.redo_label is not None and state.can_redo
        )
        self._set_issues_enabled(project_enabled)
        self._set_glossary_enabled(project_enabled)

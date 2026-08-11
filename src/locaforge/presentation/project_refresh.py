"""Build a consistent presentation snapshot for project refreshes."""

from __future__ import annotations

from dataclasses import dataclass

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import TranslationEntry
from locaforge.presentation.project_action_state import ProjectActionState


@dataclass(frozen=True, slots=True)
class ProjectRefreshSnapshot:
    has_project: bool
    entries: tuple[TranslationEntry, ...]
    documents: tuple[ProjectDocument, ...]
    action_state: ProjectActionState
    model_name: str
    project_name: str | None
    project_dirty: bool


class ProjectRefreshService:
    """Collect project state once before UI refresh callbacks mutate selection."""

    def __init__(self, workspace: ProjectWorkspace) -> None:
        self._workspace = workspace

    def snapshot(
        self, *, busy: bool, has_selected_documents: bool
    ) -> ProjectRefreshSnapshot:
        has_project = self._workspace.has_project
        project = self._workspace.project if has_project else None
        actions_enabled = has_project and not busy
        undo_label = self._workspace.next_undo_operation_label() if actions_enabled else None
        redo_label = self._workspace.next_redo_operation_label() if actions_enabled else None
        return ProjectRefreshSnapshot(
            has_project=has_project,
            entries=tuple(project.entries) if project is not None else (),
            documents=tuple(project.documents) if project is not None else (),
            action_state=ProjectActionState(
                has_project=has_project,
                busy=busy,
                has_selected_documents=has_selected_documents,
                source_format=self._workspace.source_format if has_project else None,
                undo_label=undo_label,
                can_undo=(
                    self._workspace.can_undo_last_translation()
                    if undo_label is not None
                    else False
                ),
                redo_label=redo_label,
                can_redo=(
                    self._workspace.can_redo_last_translation()
                    if redo_label is not None
                    else False
                ),
            ),
            model_name=(
                self._workspace.resolve_model_settings().model
                if has_project
                else "Not configured"
            ),
            project_name=project.name if project is not None else None,
            project_dirty=project.dirty if project is not None else False,
        )

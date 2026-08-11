from types import SimpleNamespace
from typing import Any, cast

from locaforge.domain.settings import ModelSettings
from locaforge.presentation.project_action_state import ProjectActionState
from locaforge.presentation.project_refresh import ProjectRefreshService


class WorkspaceStub:
    def __init__(self, *, has_project: bool = True) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(
            name="Demo",
            dirty=True,
            entries=[SimpleNamespace(id="entry-1")],
            documents=[SimpleNamespace(id="document-1")],
        )
        self.source_format = "json"
        self.undo_calls = 0
        self.redo_calls = 0

    def next_undo_operation_label(self) -> str | None:
        self.undo_calls += 1
        return "batch translation"

    def next_redo_operation_label(self) -> str | None:
        self.redo_calls += 1
        return "approval"

    def can_undo_last_translation(self) -> bool:
        return True

    def can_redo_last_translation(self) -> bool:
        return False

    def resolve_model_settings(self) -> ModelSettings:
        return ModelSettings(model="qwen-demo")


def test_open_project_snapshot_collects_content_and_action_state() -> None:
    workspace = WorkspaceStub()
    service = ProjectRefreshService(cast(Any, workspace))

    snapshot = service.snapshot(busy=False, has_selected_documents=True)

    assert snapshot.has_project is True
    assert [entry.id for entry in snapshot.entries] == ["entry-1"]
    assert [document.id for document in snapshot.documents] == ["document-1"]
    assert snapshot.model_name == "qwen-demo"
    assert snapshot.project_name == "Demo"
    assert snapshot.project_dirty is True
    assert snapshot.action_state == ProjectActionState(
        has_project=True,
        busy=False,
        has_selected_documents=True,
        source_format="json",
        undo_label="batch translation",
        can_undo=True,
        redo_label="approval",
        can_redo=False,
    )


def test_busy_snapshot_disables_history_queries_and_actions() -> None:
    workspace = WorkspaceStub()
    service = ProjectRefreshService(cast(Any, workspace))

    snapshot = service.snapshot(busy=True, has_selected_documents=False)

    assert snapshot.action_state.undo_label is None
    assert snapshot.action_state.redo_label is None
    assert snapshot.action_state.can_undo is False
    assert snapshot.action_state.can_redo is False
    assert workspace.undo_calls == workspace.redo_calls == 0


def test_closed_project_snapshot_uses_empty_defaults() -> None:
    workspace = WorkspaceStub(has_project=False)
    service = ProjectRefreshService(cast(Any, workspace))

    snapshot = service.snapshot(busy=False, has_selected_documents=False)

    assert snapshot.has_project is False
    assert snapshot.entries == ()
    assert snapshot.documents == ()
    assert snapshot.model_name == "Not configured"
    assert snapshot.project_name is None
    assert snapshot.project_dirty is False
    assert snapshot.action_state == ProjectActionState(
        has_project=False,
        busy=False,
        has_selected_documents=False,
        source_format=None,
    )
    assert workspace.undo_calls == workspace.redo_calls == 0


def test_missing_history_labels_do_not_query_capabilities() -> None:
    workspace = WorkspaceStub()
    workspace.next_undo_operation_label = lambda: None
    workspace.next_redo_operation_label = lambda: None
    service = ProjectRefreshService(cast(Any, workspace))

    snapshot = service.snapshot(busy=False, has_selected_documents=False)

    assert snapshot.action_state.can_undo is False
    assert snapshot.action_state.can_redo is False

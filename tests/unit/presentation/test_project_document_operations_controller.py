from types import SimpleNamespace
from typing import Any, cast

from locaforge.application.dto.project import DocumentRefreshPreview
from locaforge.presentation.project_document_operations_controller import (
    ProjectDocumentOperationsController,
)


class ExplorerStub:
    selected = frozenset({"document-1", "document-2"})

    def selected_document_ids(self) -> frozenset[str]:
        return self.selected


class WorkspaceStub:
    project = SimpleNamespace(
        entries=(
            SimpleNamespace(document_id="document-1"),
            SimpleNamespace(document_id="document-1"),
            SimpleNamespace(document_id="document-2"),
        )
    )

    def __init__(self) -> None:
        self.removed: tuple[str, ...] | None = None
        self.refreshed: tuple[str, ...] | None = None
        self.preview_error: Exception | None = None

    def remove_documents(self, document_ids: tuple[str, ...]) -> None:
        self.removed = document_ids

    def preview_document_refresh(
        self, document_ids: tuple[str, ...]
    ) -> DocumentRefreshPreview:
        if self.preview_error is not None:
            raise self.preview_error
        return DocumentRefreshPreview(len(document_ids), 1, 2, 3, 4)

    def refresh_documents(self, document_ids: tuple[str, ...]) -> None:
        self.refreshed = document_ids


def make_controller(
    workspace: WorkspaceStub,
    *,
    confirm_remove=lambda _documents, _entries: True,
    confirm_refresh=lambda _preview: True,
):
    messages: list[str] = []
    errors: list[str] = []
    cleared: list[bool] = []

    def run_action(action, message: str) -> bool:
        action()
        messages.append(message)
        return True

    controller = ProjectDocumentOperationsController(
        cast(Any, workspace),
        cast(Any, ExplorerStub()),
        run_action=run_action,
        confirm_remove=confirm_remove,
        confirm_refresh=confirm_refresh,
        show_refresh_error=errors.append,
        clear_selection=lambda: cleared.append(True),
    )
    return controller, messages, errors, cleared


def test_removes_confirmed_selection_and_clears_selection() -> None:
    workspace = WorkspaceStub()
    confirmation: list[tuple[int, int]] = []
    controller, messages, _, cleared = make_controller(
        workspace,
        confirm_remove=lambda documents, entries: (
            confirmation.append((documents, entries)) or True
        ),
    )

    controller.remove_selected()

    assert confirmation == [(2, 3)]
    assert workspace.removed is not None
    assert set(workspace.removed) == {"document-1", "document-2"}
    assert messages == ["2 project files removed"]
    assert cleared == [True]


def test_cancelled_remove_does_not_mutate_workspace() -> None:
    workspace = WorkspaceStub()
    controller, messages, _, cleared = make_controller(
        workspace, confirm_remove=lambda _documents, _entries: False
    )

    controller.remove_selected()

    assert workspace.removed is None
    assert messages == []
    assert cleared == []


def test_refresh_uses_preview_and_runs_confirmed_operation() -> None:
    workspace = WorkspaceStub()
    previews: list[DocumentRefreshPreview] = []
    controller, messages, _, _ = make_controller(
        workspace,
        confirm_refresh=lambda preview: previews.append(preview) or True,
    )

    controller.refresh_selected()

    assert previews == [DocumentRefreshPreview(2, 1, 2, 3, 4)]
    assert workspace.refreshed is not None
    assert messages == ["2 source files refreshed"]


def test_refresh_preview_failure_is_reported_without_running_action() -> None:
    workspace = WorkspaceStub()
    workspace.preview_error = ValueError("source missing")
    controller, messages, errors, _ = make_controller(workspace)

    controller.refresh_selected()

    assert errors == ["source missing"]
    assert workspace.refreshed is None
    assert messages == []

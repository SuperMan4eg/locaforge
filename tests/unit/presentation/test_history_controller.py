import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication, QListWidget, QMessageBox, QPushButton, QWidget

from locaforge.domain.history import EntryRevision, ProjectOperation
from locaforge.presentation.history_controller import HistoryController


class WorkspaceStub:
    def __init__(self) -> None:
        self.restored: tuple[str, int] | None = None

    def entry_revisions(self, entry_id: str) -> tuple[EntryRevision, ...]:
        return (
            EntryRevision(7, entry_id, "Old\ntranslation", datetime(2026, 8, 5, tzinfo=UTC)),
            EntryRevision(6, entry_id, None, datetime(2026, 8, 4, tzinfo=UTC)),
        )

    def restore_entry_revision(self, entry_id: str, revision_id: int) -> None:
        self.restored = (entry_id, revision_id)

    def project_operations(self) -> tuple[ProjectOperation, ...]:
        return (
            ProjectOperation(
                9,
                "Review translations",
                datetime(2026, 8, 6, tzinfo=UTC),
                False,
                2,
            ),
            ProjectOperation(
                8,
                "Edit translation",
                datetime(2026, 8, 5, tzinfo=UTC),
                True,
                1,
            ),
        )


def make_controller() -> tuple[
    HistoryController,
    WorkspaceStub,
    QListWidget,
    QListWidget,
    QPushButton,
    list[str],
    QWidget,
]:
    parent = QWidget()
    revisions = QListWidget(parent)
    operations = QListWidget(parent)
    restore_button = QPushButton(parent)
    messages: list[str] = []
    workspace = WorkspaceStub()

    def run(action: Callable[[], object], message: str) -> bool:
        action()
        messages.append(message)
        return True

    controller = HistoryController(
        workspace=cast(Any, workspace),
        revisions=revisions,
        operations=operations,
        restore_button=restore_button,
        run_action=run,
        current_entry_id=lambda: "entry-one",
        can_restore=lambda: True,
        parent=parent,
    )
    return controller, workspace, revisions, operations, restore_button, messages, parent


def test_refresh_formats_revisions_and_enables_selected_revision() -> None:
    application = QApplication.instance() or QApplication([])
    controller, _, revisions, operations, restore_button, _, parent = make_controller()

    controller.refresh("entry-one")
    revisions.setCurrentRow(0)

    assert application is not None
    assert parent is not None
    assert revisions.count() == 2
    assert revisions.item(0).text().endswith("| Old translation")
    assert revisions.item(1).text().endswith("| <untranslated>")
    assert operations.count() == 2
    assert operations.item(0).text().endswith(
        "| Applied | Review translations (2 entries)"
    )
    assert operations.item(1).text().endswith(
        "| Undone | Edit translation (1 entry)"
    )
    assert restore_button.isEnabled() is True


def test_restore_runs_selected_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    controller, workspace, revisions, _, _, messages, parent = make_controller()
    controller.refresh("entry-one")
    revisions.setCurrentRow(0)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    controller.restore()

    assert application is not None
    assert parent is not None
    assert workspace.restored == ("entry-one", 7)
    assert messages == ["Translation revision restored"]


def test_clear_removes_revisions_and_disables_restore() -> None:
    application = QApplication.instance() or QApplication([])
    controller, _, revisions, operations, restore_button, _, parent = make_controller()
    controller.refresh("entry-one")
    revisions.setCurrentRow(0)

    controller.clear()

    assert application is not None
    assert parent is not None
    assert revisions.count() == 0
    assert operations.count() == 0
    assert restore_button.isEnabled() is False

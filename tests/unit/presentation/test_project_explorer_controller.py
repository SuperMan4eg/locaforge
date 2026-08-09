import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QListWidget

from locaforge.application.dto.project import ProjectStatistics
from locaforge.presentation.project_explorer_controller import ProjectExplorerController


class WorkspaceStub:
    def __init__(self, has_project: bool) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(
            name="Demo",
            source_language="en",
            target_language="ru",
            documents=(
                SimpleNamespace(id="doc-1", name="strings.json", source_format="json"),
            ),
            entries=(
                SimpleNamespace(document_id="doc-1", translation="Перевод"),
                SimpleNamespace(document_id="doc-1", translation=None),
            ),
        )

    def project_statistics(self) -> ProjectStatistics:
        return ProjectStatistics(10, 3, 7, 2, 4, 1, 2, 3)


def test_empty_explorer_reports_no_open_project() -> None:
    application = QApplication.instance() or QApplication([])
    view = QListWidget()
    controller = ProjectExplorerController(cast(Any, WorkspaceStub(False)), view)

    controller.refresh()

    assert application is not None
    assert [view.item(row).text() for row in range(view.count())] == ["No project open"]


def test_explorer_renders_project_statistics() -> None:
    application = QApplication.instance() or QApplication([])
    view = QListWidget()
    controller = ProjectExplorerController(cast(Any, WorkspaceStub(True)), view)

    controller.refresh()

    assert application is not None
    assert [view.item(row).text() for row in range(view.count())] == [
        "Demo",
        "en -> ru",
        "Progress: 70% (7/10)",
        "Untranslated: 3",
        "Needs review: 2",
        "Approved: 4",
        "Errors: 1",
        "Validation issues: 3",
        "Locked: 2",
        "Files (1):",
        "  strings.json [JSON] — 1/2 translated",
    ]

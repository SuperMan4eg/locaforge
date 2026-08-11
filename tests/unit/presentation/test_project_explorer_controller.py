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


class TrackingEntry:
    def __init__(self, document_id: str, translation: str | None) -> None:
        self._document_id = document_id
        self.translation = translation
        self.document_id_reads = 0

    @property
    def document_id(self) -> str:
        self.document_id_reads += 1
        return self._document_id


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


def test_document_progress_is_collected_in_one_entry_pass() -> None:
    entries = [
        TrackingEntry(f"doc-{index % 500}", "Translated" if index % 2 else None)
        for index in range(10_000)
    ]

    progress = ProjectExplorerController._document_progress(cast(Any, entries))

    assert progress["doc-0"] == (20, 0)
    assert progress["doc-1"] == (20, 20)
    assert sum(entry.document_id_reads for entry in entries) == len(entries)


def test_explorer_preserves_document_selection_across_refresh() -> None:
    application = QApplication.instance() or QApplication([])
    view = QListWidget()
    controller = ProjectExplorerController(cast(Any, WorkspaceStub(True)), view)
    controller.refresh()
    document_item = view.item(view.count() - 1)
    document_item.setSelected(True)

    controller.refresh()

    assert application is not None
    assert controller.selected_document_ids() == frozenset({"doc-1"})

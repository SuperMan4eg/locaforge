import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QListWidget, QTreeWidget

from locaforge.application.dto.project import ProjectStatistics
from locaforge.domain.entry import TranslationEntry
from locaforge.presentation.project_explorer_controller import ProjectExplorerController
from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
from locaforge.presentation.translation_table_model import TranslationTableModel


class WorkspaceStub:
    has_project = True
    project = SimpleNamespace(
        name="Demo",
        source_language="en",
        target_language="ru",
        profile=SimpleNamespace(project_type="", description="", domain="", tone=""),
        documents=(
            SimpleNamespace(
                id="doc-1", name="one.json", source_format="json", source_path="one.json"
            ),
            SimpleNamespace(
                id="doc-2", name="two.json", source_format="json", source_path="two.json"
            ),
        ),
        entries=(),
    )

    def project_statistics(self) -> ProjectStatistics:
        return ProjectStatistics(0, 0, 0, 0, 0, 0, 0, 0)


def test_explorer_reports_multiple_selected_documents() -> None:
    application = QApplication.instance() or QApplication([])
    view = QListWidget()
    selections: list[frozenset[str]] = []
    controller = ProjectExplorerController(
        cast(Any, WorkspaceStub()), view, selections.append
    )
    controller.refresh()

    view.item(view.count() - 2).setSelected(True)
    view.item(view.count() - 1).setSelected(True)

    assert application is not None
    assert controller.selected_document_ids() == frozenset({"doc-1", "doc-2"})
    assert selections[-1] == frozenset({"doc-1", "doc-2"})


def test_proxy_filters_by_multiple_project_documents() -> None:
    application = QApplication.instance() or QApplication([])
    source = TranslationTableModel()
    entries = [
        TranslationEntry("one", ("one",), "One", document_id="doc-1"),
        TranslationEntry("two", ("two",), "Two", document_id="doc-2"),
    ]
    source.set_entries(entries)
    proxy = TranslationFilterProxyModel()
    proxy.setSourceModel(source)

    proxy.set_document_ids(("doc-1", "doc-2"))

    assert application is not None
    assert proxy.rowCount() == 2


def test_project_tree_groups_documents_and_selects_folder() -> None:
    application = QApplication.instance() or QApplication([])
    workspace = WorkspaceStub()
    workspace.project.documents = (
        SimpleNamespace(
            id="doc-1", name="one.json", source_format="json", source_path="ui/one.json"
        ),
        SimpleNamespace(
            id="doc-2", name="two.json", source_format="json", source_path="ui/two.json"
        ),
    )
    view = QListWidget()
    tree = QTreeWidget()
    selections: list[frozenset[str]] = []
    controller = ProjectExplorerController(
        cast(Any, workspace), view, selections.append, file_tree=tree
    )

    controller.refresh()
    folder = tree.topLevelItem(0)
    folder.setSelected(True)

    assert application is not None
    assert folder.text(0) == "ui"
    assert folder.childCount() == 2
    assert controller.selected_document_ids() == frozenset({"doc-1", "doc-2"})
    assert selections[-1] == frozenset({"doc-1", "doc-2"})


def test_project_tree_filters_paths_and_folder_selection_to_visible_files() -> None:
    application = QApplication.instance() or QApplication([])
    workspace = WorkspaceStub()
    workspace.project.documents = (
        SimpleNamespace(
            id="doc-1", name="menu.json", source_format="json", source_path="ui/menu.json"
        ),
        SimpleNamespace(
            id="doc-2",
            name="errors.json",
            source_format="json",
            source_path="system/errors.json",
        ),
    )
    tree = QTreeWidget()
    controller = ProjectExplorerController(
        cast(Any, workspace), QListWidget(), file_tree=tree
    )
    controller.refresh()

    controller.set_file_filter("menu")

    ui_folder = tree.topLevelItem(0)
    system_folder = tree.topLevelItem(1)
    assert application is not None
    assert ui_folder.isHidden() is False
    assert system_folder.isHidden() is True
    assert controller.visible_document_ids() == frozenset({"doc-1"})
    ui_folder.setSelected(True)
    assert controller.selected_document_ids() == frozenset({"doc-1"})

    tree.clearSelection()
    controller.select_visible_documents()
    assert controller.selected_document_ids() == frozenset({"doc-1"})

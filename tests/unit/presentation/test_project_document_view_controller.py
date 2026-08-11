import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QMainWindow

from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project
from locaforge.presentation.project_document_view_controller import (
    ProjectDocumentViewController,
)
from locaforge.presentation.project_workspace_widgets import (
    build_project_workspace_widgets,
)


class ExplorerStub:
    def __init__(self) -> None:
        self.selected = frozenset({"document-1"})
        self.visible = frozenset({"document-1"})
        self.filter_text = ""

    def selected_document_ids(self) -> frozenset[str]:
        return self.selected

    def visible_document_ids(self) -> frozenset[str]:
        return self.visible

    def set_file_filter(self, text: str) -> None:
        self.filter_text = text

    def select_documents(self, document_ids: tuple[str, ...]) -> None:
        self.selected = frozenset(document_ids)

    def select_visible_documents(self) -> None:
        self.selected = self.visible


def test_coordinates_selection_counts_details_and_opening(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    source = tmp_path / "dialog.json"
    document = ProjectDocument(
        "document-1",
        "dialog.json",
        "ui/dialog.json",
        "json",
        {},
        str(source),
    )
    project = Project(
        "project-1",
        "Game",
        "en",
        "ru",
        entries=[
            TranslationEntry(
                "entry-1",
                ("hello",),
                "Hello",
                "Привет",
                EntryStatus.APPROVED,
                True,
                document_id=document.id,
            )
        ],
        documents=[document],
    )
    workspace = SimpleNamespace(has_project=True, project=project)
    explorer = ExplorerStub()
    filters: list[frozenset[str]] = []
    opened: list[bool] = []
    source_paths: list[Path] = []
    commands: list[str] = []
    widgets = build_project_workspace_widgets(
        window,
        add_files=lambda: None,
        add_folder=lambda: None,
        export_selected=lambda: None,
        remove_selected=lambda: None,
        refresh_selected=lambda: None,
        edit_settings=lambda: None,
        preview_context=lambda: None,
        show_context_menu=lambda _point: None,
        open_document=lambda _document_id: None,
    )
    try:
        controller = ProjectDocumentViewController(
            cast(Any, workspace),
            cast(Any, explorer),
            widgets,
            set_document_filter=filters.append,
            is_busy=lambda: False,
            show_translations=lambda: opened.append(True),
            open_source_path=source_paths.append,
            refresh_selected=lambda: commands.append("refresh"),
            export_selected=lambda: commands.append("export"),
            remove_selected=lambda: commands.append("remove"),
            add_files=lambda: commands.append("files"),
            add_folder=lambda: commands.append("folder"),
            edit_settings=lambda: commands.append("settings"),
        )

        controller.selection_changed(frozenset({document.id}))

        assert filters == [frozenset({document.id})]
        assert widgets.export_selected_button.isEnabled() is True
        assert widgets.file_count.text() == "1 / 1 files · 1 selected"
        assert "dialog.json" in widgets.file_details.text()
        assert "Translated: 1 (100%)" in widgets.file_details.text()
        assert "Approved: 1" in widgets.file_details.text()
        assert controller.selected_source_location(frozenset({document.id})) == source

        controller.filter_files("dialog")
        assert explorer.filter_text == "dialog"
        controller.open_document(document.id)
        assert explorer.selected == frozenset({document.id})
        assert opened == [True]

        menu = controller.build_context_menu()
        actions = {action.text(): action for action in menu.actions()}
        assert actions["Open translations"].isEnabled() is True
        assert actions["Open source location"].isEnabled() is True
        assert actions["Refresh from source..."].isEnabled() is True
        actions["Open source location"].trigger()
        actions["Refresh from source..."].trigger()
        actions["Export selected..."].trigger()
        actions["Remove from project..."].trigger()
        actions["Add files..."].trigger()
        actions["Add folder..."].trigger()
        actions["Project settings..."].trigger()
        assert source_paths == [source]
        assert commands == [
            "refresh",
            "export",
            "remove",
            "files",
            "folder",
            "settings",
        ]
    finally:
        window.close()
        application.processEvents()


def test_empty_selection_disables_document_commands() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    widgets = build_project_workspace_widgets(
        window,
        add_files=lambda: None,
        add_folder=lambda: None,
        export_selected=lambda: None,
        remove_selected=lambda: None,
        refresh_selected=lambda: None,
        edit_settings=lambda: None,
        preview_context=lambda: None,
        show_context_menu=lambda _point: None,
        open_document=lambda _document_id: None,
    )
    try:
        controller = ProjectDocumentViewController(
            cast(Any, SimpleNamespace(has_project=False)),
            cast(Any, ExplorerStub()),
            widgets,
            set_document_filter=lambda _ids: None,
            is_busy=lambda: False,
            show_translations=lambda: None,
        )

        controller.selection_changed(frozenset())

        assert widgets.export_selected_button.isEnabled() is False
        assert widgets.remove_selected_button.isEnabled() is False
        assert widgets.refresh_selected_button.isEnabled() is False
        assert widgets.file_count.text() == "1 / 0 files"
        assert widgets.file_details.text().startswith("Select one or more project files")
    finally:
        window.close()
        application.processEvents()

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QTreeWidgetItem

from locaforge.presentation.project_workspace_widgets import (
    build_project_workspace_widgets,
)


def test_builds_project_workspace_and_connects_local_interactions() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[object] = []
    try:
        widgets = build_project_workspace_widgets(
            window,
            add_files=lambda: calls.append("files"),
            add_folder=lambda: calls.append("folder"),
            export_selected=lambda: calls.append("export"),
            remove_selected=lambda: calls.append("remove"),
            refresh_selected=lambda: calls.append("refresh"),
            edit_settings=lambda: calls.append("settings"),
            preview_context=lambda: calls.append("context"),
            show_context_menu=lambda point: calls.append(("menu", point)),
            open_document=lambda document_id: calls.append(("open", document_id)),
        )

        assert widgets.file_tree.columnCount() == 3
        assert [widgets.file_tree.headerItem().text(index) for index in range(3)] == [
            "Name",
            "Format",
            "Progress",
        ]
        assert widgets.file_search.isClearButtonEnabled() is True
        assert widgets.file_count.text() == "0 / 0 files"
        assert widgets.content.count() == 2

        widgets.add_files_button.click()
        widgets.add_folder_button.click()
        widgets.export_selected_button.click()
        widgets.remove_selected_button.click()
        widgets.refresh_selected_button.click()
        widgets.settings_button.click()
        widgets.context_button.click()
        point = QPoint(2, 3)
        widgets.file_tree.customContextMenuRequested.emit(point)
        item = QTreeWidgetItem(["dialog.json", "JSON", "0%"])
        item.setData(0, Qt.ItemDataRole.UserRole, "document-1")
        widgets.file_tree.addTopLevelItem(item)
        widgets.file_tree.itemDoubleClicked.emit(item, 0)

        assert calls == [
            "files",
            "folder",
            "export",
            "remove",
            "refresh",
            "settings",
            "context",
            ("menu", point),
            ("open", "document-1"),
        ]
    finally:
        window.close()
        application.processEvents()

"""File menu actions and format-specific export commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu


@dataclass(frozen=True, slots=True)
class FileActions:
    menu: QMenu
    recent_projects_menu: QMenu
    new_project: QAction
    open_project: QAction
    import_files: QAction
    import_folder: QAction
    save: QAction
    save_as: QAction
    export_selected: QAction
    export_all: QAction
    export_json: QAction
    export_po: QAction
    export_csv: QAction
    export_xml: QAction
    exit: QAction


def build_file_actions(
    window: QMainWindow,
    *,
    new_project: Callable[[], None],
    open_project: Callable[[], None],
    import_files: Callable[[], None],
    import_folder: Callable[[], None],
    save: Callable[[], None],
    save_as: Callable[[], None],
    export_selected: Callable[[], None],
    export_all: Callable[[], None],
    export_json: Callable[[], None],
    export_po: Callable[[], None],
    export_csv: Callable[[], None],
    export_xml: Callable[[], None],
) -> FileActions:
    """Create the File menu and all file-format export commands."""
    menu = window.menuBar().addMenu("&File")
    new_action = QAction("&New project...", window)
    new_action.setShortcut(QKeySequence.StandardKey.New)
    new_action.setToolTip("Create an empty project before adding files")
    new_action.triggered.connect(new_project)

    open_action = QAction("&Open project...", window)
    open_action.setShortcut(QKeySequence.StandardKey.Open)
    open_action.triggered.connect(open_project)

    import_files_action = QAction("&Import files...", window)
    import_files_action.setToolTip(
        "Add one or more JSON, CSV/TSV, PO, or XML files to the current project"
    )
    import_files_action.setShortcut(QKeySequence("Ctrl+I"))
    import_files_action.triggered.connect(import_files)

    import_folder_action = QAction("Import &folder...", window)
    import_folder_action.setToolTip(
        "Recursively add supported localization files from a folder"
    )
    import_folder_action.triggered.connect(import_folder)

    save_action = QAction("&Save", window)
    save_action.setShortcut(QKeySequence.StandardKey.Save)
    save_action.triggered.connect(save)
    save_as_action = QAction("Save &As...", window)
    save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
    save_as_action.triggered.connect(save_as)

    export_selected_action = QAction(
        "Export &selected project files...", window
    )
    export_selected_action.setToolTip(
        "Export the files selected in the Project tab in their original formats"
    )
    export_selected_action.triggered.connect(export_selected)
    export_all_action = QAction("Export &all project files...", window)
    export_all_action.setToolTip(
        "Export every document with its original file name and format"
    )
    export_all_action.triggered.connect(export_all)

    export_json_action = QAction("&Export JSON...", window)
    export_json_action.setShortcut(QKeySequence("Ctrl+E"))
    export_json_action.triggered.connect(export_json)
    export_po_action = QAction("Export &PO...", window)
    export_po_action.triggered.connect(export_po)
    export_csv_action = QAction("Export &CSV/TSV...", window)
    export_csv_action.triggered.connect(export_csv)
    export_xml_action = QAction("Export &XML...", window)
    export_xml_action.triggered.connect(export_xml)

    exit_action = QAction("E&xit", window)
    exit_action.triggered.connect(window.close)

    menu.addAction(new_action)
    menu.addAction(open_action)
    recent_menu = menu.addMenu("Recent projects")
    menu.addSeparator()
    menu.addAction(import_files_action)
    menu.addAction(import_folder_action)
    menu.addSeparator()
    menu.addAction(save_action)
    menu.addAction(save_as_action)
    menu.addAction(export_selected_action)
    menu.addAction(export_all_action)
    menu.addSeparator()
    menu.addAction(exit_action)

    return FileActions(
        menu,
        recent_menu,
        new_action,
        open_action,
        import_files_action,
        import_folder_action,
        save_action,
        save_as_action,
        export_selected_action,
        export_all_action,
        export_json_action,
        export_po_action,
        export_csv_action,
        export_xml_action,
        exit_action,
    )

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDockWidget

from locaforge.app.bootstrap import build_workspace
from locaforge.presentation.main_window import MainWindow
from locaforge.presentation.recent_projects import RecentProjectsStore
from locaforge.presentation.window_layout import WindowLayoutStore


def make_window(tmp_path: Path) -> tuple[MainWindow, QApplication]:
    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    settings.clear()
    window = MainWindow(
        build_workspace(tmp_path / "data"),
        layout_store=WindowLayoutStore(settings),
        recent_projects=RecentProjectsStore(settings),
    )
    return window, application


def test_main_window_composes_all_docks_and_menus(tmp_path: Path) -> None:
    window, application = make_window(tmp_path)
    try:
        window.show()
        application.processEvents()

        dock_titles = {dock.windowTitle() for dock in window.findChildren(QDockWidget)}
        menu_titles = {action.text() for action in window.menuBar().actions()}

        assert window.windowTitle() == "LocaForge"
        assert window.centralWidget() is not None
        assert dock_titles == {
            "Project Explorer",
            "Validation",
            "History",
            "Logs",
            "Translation Memory",
            "Glossary",
        }
        assert menu_titles == {
            "&File",
            "&Edit",
            "&Review",
            "&Models",
            "&Navigate",
            "&Tools",
            "&View",
        }
    finally:
        window.close()
        application.processEvents()


def test_main_window_renders_preloaded_project(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "project-ui.ini"), QSettings.Format.IniFormat)
    settings.clear()
    workspace = build_workspace(tmp_path / "data")
    source = tmp_path / "dialog.json"
    source.write_text('{"hello": "Hello", "exit": "Exit"}', encoding="utf-8")
    workspace.create_from_json(
        source,
        tmp_path / "dialog.lfproj",
        "en",
        "ru",
    )
    window = MainWindow(
        workspace,
        layout_store=WindowLayoutStore(settings),
        recent_projects=RecentProjectsStore(settings),
    )
    try:
        window.show()
        application.processEvents()

        explorer_lines = [
            window._project_explorer.item(row).text()
            for row in range(window._project_explorer.count())
        ]

        assert window._model.rowCount() == 2
        assert window._proxy_model.rowCount() == 2
        assert window.windowTitle() == "LocaForge — dialog"
        assert explorer_lines[:3] == [
            "dialog",
            "en -> ru",
            "Progress: 0% (0/2)",
        ]
        assert "Files (1):" in explorer_lines
        assert any("dialog.json [JSON]" in line for line in explorer_lines)
        assert window._table.currentIndex().isValid()
        assert window._source_editor.toPlainText() == "Hello"
    finally:
        window.close()
        application.processEvents()

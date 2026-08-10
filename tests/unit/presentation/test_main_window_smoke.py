import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDockWidget, QTabWidget

from locaforge.app.bootstrap import build_workspace
from locaforge.presentation import main_window as main_window_module
from locaforge.presentation.localization import LocalizationManager
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
        menu_actions = window.menuBar().actions()
        menu_titles = {action.text() for action in menu_actions}
        file_action = next(action for action in menu_actions if action.text() == "&File")
        file_menu = file_action.menu()
        assert file_menu is not None
        file_actions = {action.text() for action in file_menu.actions()}
        tools_action = next(action for action in menu_actions if action.text() == "&Tools")
        tools_menu = tools_action.menu()
        assert tools_menu is not None
        tools_actions = {action.text() for action in tools_menu.actions()}

        assert window.windowTitle() == "LocaForge"
        assert window.centralWidget() is not None
        assert dock_titles == {
            "Validation",
            "History",
            "Logs",
            "Translation Memory",
            "Glossary",
        }
        tabs = window.findChild(QTabWidget)
        assert tabs is not None
        assert [tabs.tabText(index) for index in range(tabs.count())] == [
            "Translations",
            "Project",
        ]
        assert menu_titles == {
            "&File",
            "&Edit",
            "&Review",
            "&Navigate",
            "&Tools",
            "&View",
        }
        assert "&Import files..." in file_actions
        assert "Import &folder..." in file_actions
        assert "Export &selected project files..." in file_actions
        assert "Export &all project files..." in file_actions
        assert "Ollama Setup..." not in tools_actions
        assert not any(
            legacy in file_actions
            for legacy in (
                "&Import JSON...",
                "Import &PO...",
                "Import CSV/&TSV...",
                "Import &XML...",
                "&Export JSON...",
                "Export &PO...",
                "Export &CSV/TSV...",
                "Export &XML...",
            )
        )
    finally:
        window.close()
        application.processEvents()


def test_ollama_checks_do_not_replace_active_workspace_client(
    tmp_path: Path, monkeypatch
) -> None:
    window, application = make_window(tmp_path)
    original_client = window._workspace._llm_client

    class ProbeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        def health_check(self) -> bool:
            return True

        def list_models(self) -> tuple[str, ...]:
            return ("model",)

        def pull_model(self, model: str) -> None:
            pulled.append((self.server_url, model))

    monkeypatch.setattr(main_window_module, "OllamaClient", ProbeClient)
    pulled: list[tuple[str, str]] = []
    operations = []
    monkeypatch.setattr(
        window._model_pull,
        "start",
        lambda model, operation=None: operations.append((model, operation)) or True,
    )
    try:
        assert window._ollama_connection_test("http://probe:11434") == (True, "Connected")
        assert window._ollama_models("http://probe:11434") == ("model",)
        assert window._pull_model_from_settings("http://download:11434", "model") is True
        assert operations[0][0] == "model"
        operations[0][1]()
        assert pulled == [("http://download:11434", "model")]
        assert window._workspace._llm_client is original_client
    finally:
        window.close()
        application.processEvents()


def test_main_window_smoke_in_english_and_russian(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    for locale, expected_menu, expected_tab in (
        ("en", "&File", "Translations"),
        ("ru", "&Файл", "Переводы"),
    ):
        settings = QSettings(
            str(tmp_path / f"ui-{locale}.ini"), QSettings.Format.IniFormat
        )
        settings.clear()
        window = MainWindow(
            build_workspace(tmp_path / f"data-{locale}"),
            layout_store=WindowLayoutStore(settings),
            recent_projects=RecentProjectsStore(settings),
            localization=LocalizationManager(tmp_path / f"locales-{locale}", locale),
        )
        try:
            window.show()
            application.processEvents()

            assert not hasattr(window, "_settings_button")
            assert window.menuBar().actions()[0].text() == expected_menu
            assert window._workspace_tabs.tabText(0) == expected_tab
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
        assert window._project_file_tree.topLevelItemCount() == 1
        assert window._project_file_tree.topLevelItem(0).text(0) == "dialog.json"
        assert window._project_file_tree.topLevelItem(0).text(1) == "JSON"
        assert window._project_file_count.text() == "1 / 1 files"
        assert window._table.currentIndex().isValid()
        assert window._source_editor.toPlainText() == "Hello"
    finally:
        window.close()
        application.processEvents()


def test_main_window_copies_diagnostics_without_project_content(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "diagnostics-ui.ini"), QSettings.Format.IniFormat)
    workspace = build_workspace(tmp_path / "data")
    source = tmp_path / "private-location.json"
    source.write_text('{"private-key": "Secret source text"}', encoding="utf-8")
    workspace.create_from_json(
        source,
        tmp_path / "Confidential project.lfproj",
        "en",
        "ru",
    )
    window = MainWindow(
        workspace,
        layout_store=WindowLayoutStore(settings),
        recent_projects=RecentProjectsStore(settings),
    )
    try:
        window._copy_diagnostics_button.click()
        report = application.clipboard().text()

        assert "project_open: true" in report
        assert "document_count: 1" in report
        assert "entry_count: 1" in report
        assert "source_formats: json" in report
        assert "Confidential project" not in report
        assert "private-location" not in report
        assert "private-key" not in report
        assert "Secret source text" not in report
    finally:
        window.close()
        application.processEvents()


def test_main_window_names_next_undo_and_redo_actions(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "history-ui.ini"), QSettings.Format.IniFormat)
    workspace = build_workspace(tmp_path / "data")
    source = tmp_path / "dialog.json"
    source.write_text('{"hello": "Hello"}', encoding="utf-8")
    project = workspace.create_from_json(
        source, tmp_path / "dialog.lfproj", "en", "ru"
    )
    workspace.edit_translation(project.entries[0].id, "Translation")
    window = MainWindow(
        workspace,
        layout_store=WindowLayoutStore(settings),
        recent_projects=RecentProjectsStore(settings),
    )
    try:
        window.show()
        application.processEvents()
        assert window._undo_translation_action.text() == "Undo Edit translation"

        window._undo_last_translation()
        application.processEvents()
        assert window._redo_translation_action.text() == "Redo Edit translation"
    finally:
        workspace.save()
        window.close()
        application.processEvents()


def test_project_tab_shortcuts_target_file_search_and_visible_files(tmp_path: Path) -> None:
    window, application = make_window(tmp_path)
    try:
        window.show()
        window._workspace_tabs.setCurrentIndex(1)
        window._focus_active_search()
        application.processEvents()

        assert window._project_file_search.hasFocus()
        window._project_file_search.setText("menu")
        window._clear_project_filter_or_selection()
        assert window._project_file_search.text() == ""
    finally:
        window.close()
        application.processEvents()

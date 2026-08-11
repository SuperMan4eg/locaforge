import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow

from locaforge.presentation.file_actions import build_file_actions


def test_builds_project_first_file_menu_and_connects_callbacks() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[str] = []

    def callback(name: str):
        return lambda: calls.append(name)

    try:
        actions = build_file_actions(
            window,
            new_project=callback("new"),
            open_project=callback("open"),
            import_files=callback("import"),
            import_folder=callback("folder"),
            save=callback("save"),
            save_as=callback("save-as"),
            export_selected=callback("selected"),
            export_all=callback("all"),
            export_json=callback("json"),
            export_po=callback("po"),
            export_csv=callback("csv"),
            export_xml=callback("xml"),
        )

        visible = {
            action.text()
            for action in actions.menu.actions()
            if not action.isSeparator()
        }
        assert "&Import files..." in visible
        assert "Import &folder..." in visible
        assert "Export &selected project files..." in visible
        assert "Export &all project files..." in visible
        assert "&Export JSON..." not in visible
        assert actions.new_project.shortcut() == QKeySequence.StandardKey.New
        assert actions.save.shortcut() == QKeySequence.StandardKey.Save
        assert actions.export_json.shortcut() == QKeySequence("Ctrl+E")

        actions.new_project.trigger()
        actions.import_files.trigger()
        actions.save.trigger()
        actions.export_json.trigger()
        assert calls == ["new", "import", "save", "json"]
    finally:
        window.close()
        application.processEvents()

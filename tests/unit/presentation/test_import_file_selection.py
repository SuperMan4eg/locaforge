import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
)

from locaforge.presentation.import_file_selection import (
    collect_import_files,
    duplicate_import_names,
    project_import_paths,
)
from locaforge.presentation.import_files_preview_dialog import ImportFilesPreviewDialog


def test_collect_import_files_expands_folders_and_ignores_unsupported(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    json_file = tmp_path / "menus.JSON"
    po_file = nested / "dialog.po"
    ignored = nested / "notes.txt"
    json_file.write_text("{}", encoding="utf-8")
    po_file.write_text("", encoding="utf-8")
    ignored.write_text("ignore", encoding="utf-8")

    result = collect_import_files((tmp_path, json_file))

    assert set(result) == {json_file.resolve(), po_file.resolve()}


def test_duplicate_import_names_are_case_insensitive(tmp_path: Path) -> None:
    first = tmp_path / "one" / "Strings.json"
    second = tmp_path / "two" / "strings.JSON"

    assert duplicate_import_names((first, second)) == frozenset({"strings.JSON"})


def test_preview_blocks_duplicate_file_names(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    paths = (tmp_path / "one" / "strings.json", tmp_path / "two" / "strings.json")
    dialog = ImportFilesPreviewDialog(paths)
    buttons = dialog.findChild(QDialogButtonBox)

    assert application is not None
    assert buttons is not None
    assert not buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert "unique relative paths" in dialog.warning.text()

    table = dialog.findChild(QTableWidget)
    assert table is not None
    table.item(1, 0).setText("dialogs/strings.json")

    assert buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert dialog.warning.text() == ""
    assert dialog.project_paths()[paths[1]] == "dialogs/strings.json"


def test_preview_blocks_paths_already_in_project(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "strings.json"
    dialog = ImportFilesPreviewDialog(
        (path,), {path: "ui/strings.json"}, ("UI/Strings.JSON",)
    )
    buttons = dialog.findChild(QDialogButtonBox)

    assert application is not None
    assert buttons is not None
    assert not buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert "already in project: ui/strings.json" in dialog.warning.text()


def test_preview_blocks_unsafe_project_paths(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "strings.json"
    dialog = ImportFilesPreviewDialog((path,))
    buttons = dialog.findChild(QDialogButtonBox)
    table = dialog.findChild(QTableWidget)

    assert application is not None
    assert buttons is not None
    assert table is not None
    table.item(0, 0).setText("../strings.json")

    assert not buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert "unsafe or empty paths" in dialog.warning.text()


def test_preview_applies_destination_folder_to_all_paths(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    paths = (tmp_path / "strings.json", tmp_path / "dialog.po")
    dialog = ImportFilesPreviewDialog(paths)
    destination = dialog.findChild(QLineEdit, "importDestinationFolder")
    apply_button = dialog.findChild(QPushButton, "applyImportDestination")

    assert application is not None
    assert destination is not None
    assert apply_button is not None
    destination.setText("locale\\ru/")
    apply_button.click()

    assert dialog.project_paths() == {
        paths[0]: "locale/ru/strings.json",
        paths[1]: "locale/ru/dialog.po",
    }


def test_preview_rejects_unsafe_destination_folder(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    dialog = ImportFilesPreviewDialog((tmp_path / "strings.json",))
    destination = dialog.findChild(QLineEdit, "importDestinationFolder")
    apply_button = dialog.findChild(QPushButton, "applyImportDestination")

    assert application is not None
    assert destination is not None
    assert apply_button is not None
    destination.setText("../outside")

    assert not apply_button.isEnabled()


def test_project_import_paths_preserve_selected_folder_structure(tmp_path: Path) -> None:
    root = tmp_path / "locales"
    first = root / "ui" / "strings.json"
    second = root / "dialogs" / "strings.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    paths = project_import_paths((first, second), (root,))

    assert paths[first.resolve()] == "ui/strings.json"
    assert paths[second.resolve()] == "dialogs/strings.json"

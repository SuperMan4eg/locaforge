import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox

from locaforge.presentation.project_setup_dialog import ProjectSetupDialog


def make_dialog() -> ProjectSetupDialog:
    return ProjectSetupDialog(
        Path("strings.json"),
        Path("game.lfproj"),
        "JSON",
        "Source: source; target: target; key: id",
    )


def test_project_setup_exposes_defaults_and_import_summary() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = make_dialog()

    assert application is not None
    assert dialog.language_pair() == ("en", "ru")
    labels = {label.text() for label in dialog.findChildren(QLabel)}
    assert dialog.windowTitle() == "Create LocaForge project"
    assert "JSON" in labels
    assert "Source: source; target: target; key: id" in labels


def test_project_setup_rejects_identical_languages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    dialog = make_dialog()
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )
    dialog.target_language.setText("EN")

    dialog.accept()

    assert application is not None
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert warnings == ["Source and target languages must be different."]


def test_project_setup_returns_trimmed_language_codes() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = make_dialog()
    dialog.source_language.setText(" en-US ")
    dialog.target_language.setText(" uk ")

    assert application is not None
    assert dialog.language_pair() == ("en-US", "uk")

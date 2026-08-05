import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox, QWidget

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.presentation.import_mapping_controller import ImportMappingController
from locaforge.presentation.json_import_profiles import JsonImportProfile


class WorkspaceStub:
    json_fields: tuple[str, ...] = ()
    csv_fields: tuple[str, ...] = ()
    xml_attributes: tuple[str, ...] = ()

    def inspect_json_fields(self, path: Path) -> tuple[str, ...]:
        return self.json_fields

    def inspect_csv_fields(self, path: Path) -> tuple[str, ...]:
        return self.csv_fields

    def inspect_xml_attribute_names(self, path: Path) -> tuple[str, ...]:
        return self.xml_attributes


class ProfileStoreStub:
    def __init__(self, profiles: tuple[JsonImportProfile, ...] = ()) -> None:
        self.profiles = profiles
        self.saved: list[JsonImportProfile] = []

    def list_profiles(self) -> tuple[JsonImportProfile, ...]:
        return self.profiles

    def save(self, profile: JsonImportProfile) -> None:
        self.saved.append(profile)


def make_controller(
    workspace: WorkspaceStub, profiles: ProfileStoreStub | None = None
) -> tuple[ImportMappingController, QWidget]:
    parent = QWidget()
    controller = ImportMappingController(
        cast(Any, workspace), cast(Any, profiles or ProfileStoreStub()), parent
    )
    return controller, parent


def test_json_without_object_fields_uses_default_import() -> None:
    application = QApplication.instance() or QApplication([])
    controller, parent = make_controller(WorkspaceStub())

    assert controller.ask_json(Path("strings.json")) is None
    assert application is not None
    assert parent is not None


def test_compatible_json_profile_can_be_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    workspace = WorkspaceStub()
    workspace.json_fields = ("key", "source", "target")
    mapping = JsonFieldMapping("source", "target", "key")
    controller, parent = make_controller(
        workspace, ProfileStoreStub((JsonImportProfile("Game", mapping),))
    )
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Game", True))

    assert controller.ask_json(Path("strings.json")) == mapping
    assert application is not None
    assert parent is not None


def test_csv_mapping_collects_source_target_and_generated_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    workspace = WorkspaceStub()
    workspace.csv_fields = ("id", "source", "target")
    controller, parent = make_controller(workspace)
    answers = iter((("source", True), ("target", True), ("<generated row>", True)))
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: next(answers))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
    )

    result = controller.ask_csv(Path("strings.csv"))

    assert result == CsvFieldMapping("source", "target", None, True)
    assert application is not None
    assert parent is not None


def test_unknown_xml_attribute_is_rejected_and_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    workspace = WorkspaceStub()
    workspace.xml_attributes = ("title", "label")
    controller, parent = make_controller(workspace)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("title, missing", True))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )

    assert controller.ask_xml(Path("strings.xml")) is None
    assert warnings == ["Unknown attribute names: missing"]
    assert application is not None
    assert parent is not None

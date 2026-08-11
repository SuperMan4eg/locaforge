from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.presentation.project_creation_import_controller import (
    ProjectCreationImportController,
)

DEFAULT_CSV_MAPPING = CsvFieldMapping("source", "target")


class ProjectIoStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str) -> Callable[..., bool]:
        def record(*args: object) -> bool:
            self.calls.append((name, args))
            return True

        return record


def make_controller(
    project_io: ProjectIoStub,
    *,
    source: Path | None = Path("source.data"),
    destination: Path | None = Path("project.lfproj"),
    languages: tuple[str, str] | None = ("en", "ru"),
    confirm_unsaved: bool = True,
    json_mapping: JsonFieldMapping | None = None,
    csv_mapping: CsvFieldMapping | None = DEFAULT_CSV_MAPPING,
    xml_mapping: XmlFieldMapping | None = None,
):
    source_requests: list[tuple[str, str]] = []
    setups: list[tuple[Path, Path, str, str]] = []
    confirmations: list[bool] = []

    def choose_source(title: str, file_filter: str) -> Path | None:
        source_requests.append((title, file_filter))
        return source

    def setup(
        source_path: Path, destination_path: Path, source_format: str, description: str
    ) -> tuple[str, str] | None:
        setups.append((source_path, destination_path, source_format, description))
        return languages

    def confirm() -> bool:
        confirmations.append(True)
        return confirm_unsaved

    controller = ProjectCreationImportController(
        cast(Any, project_io),
        choose_source=choose_source,
        choose_destination=lambda: destination,
        ask_project_setup=setup,
        confirm_unsaved_changes=confirm,
        ask_json_mapping=lambda _path: json_mapping,
        ask_csv_mapping=lambda _path: csv_mapping,
        ask_xml_mapping=lambda _path: xml_mapping,
    )
    return controller, source_requests, setups, confirmations


def test_json_import_uses_automatic_mapping_description() -> None:
    project_io = ProjectIoStub()
    controller, requests, setups, _ = make_controller(project_io)

    controller.import_json()

    assert requests == [("Import JSON", "JSON files (*.json)")]
    assert setups[0][2:] == (
        "JSON",
        "Automatic: every string value is translated and its JSON path is used as the key",
    )
    assert project_io.calls == [
        (
            "create_from_json",
            (Path("source.data"), Path("project.lfproj"), "en", "ru", None),
        )
    ]


def test_format_mappings_are_described_and_delegated() -> None:
    json_mapping = JsonFieldMapping("original", "localized", "id")
    csv_mapping = CsvFieldMapping("source", "target")
    xml_mapping = XmlFieldMapping(("title", "label"))
    project_io = ProjectIoStub()
    json_controller, _, json_setups, _ = make_controller(
        project_io, json_mapping=json_mapping
    )
    csv_controller, _, csv_setups, _ = make_controller(
        project_io, csv_mapping=csv_mapping
    )
    xml_controller, _, xml_setups, _ = make_controller(
        project_io, xml_mapping=xml_mapping
    )

    json_controller.import_json()
    csv_controller.import_csv()
    xml_controller.import_xml()

    assert json_setups[0][3] == "Source: original; target: localized; key: id"
    assert csv_setups[0][3] == "Source: source; target: target; key: generated row number"
    assert xml_setups[0][3] == "Element text nodes and attributes: title, label"
    assert [name for name, _ in project_io.calls] == [
        "create_from_json",
        "create_from_csv",
        "create_from_xml",
    ]


def test_po_import_uses_gettext_description_and_delegates() -> None:
    project_io = ProjectIoStub()
    controller, requests, setups, _ = make_controller(project_io)

    controller.import_po()

    assert requests == [("Import PO", "Gettext PO files (*.po)")]
    assert setups[0][2] == "PO"
    assert "comments/context are preserved" in setups[0][3]
    assert project_io.calls == [
        (
            "create_from_po",
            (Path("source.data"), Path("project.lfproj"), "en", "ru"),
        )
    ]


def test_cancelled_source_csv_mapping_setup_or_unsaved_confirmation_stops_import() -> None:
    project_io = ProjectIoStub()
    no_source, _, _, _ = make_controller(project_io, source=None)
    no_mapping, _, _, _ = make_controller(project_io, csv_mapping=None)
    no_setup, _, _, no_setup_confirmations = make_controller(project_io, languages=None)
    declined, _, _, declined_confirmations = make_controller(
        project_io, confirm_unsaved=False
    )

    no_source.import_json()
    no_mapping.import_csv()
    no_setup.import_po()
    declined.import_xml()

    assert no_setup_confirmations == []
    assert declined_confirmations == [True]
    assert project_io.calls == []

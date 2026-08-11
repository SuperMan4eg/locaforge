from pathlib import Path

import pytest

from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.application.project_session import ProjectSession
from locaforge.application.services.source_import import SourceImportService
from locaforge.domain.project import Project


class JsonImporter:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, object]] = []

    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
        field_mapping: object = None,
    ) -> Project:
        self.calls.append((path, field_mapping))
        return Project(
            f"imported-{len(self.calls)}",
            path.name,
            source_language,
            target_language,
            source_document={},
        )

    def inspect_fields(self, path: Path) -> tuple[str, ...]:
        self.calls.append((path, "inspect"))
        return ("key", "source", "target")


class Repository:
    def __init__(self) -> None:
        self.saved: list[Project] = []

    def save(self, project: Project) -> None:
        self.saved.append(project)


def make_service(importer: JsonImporter) -> SourceImportService:
    return SourceImportService(importer, object(), object())  # type: ignore[arg-type]


def test_imports_json_and_serializes_round_trip_mapping(tmp_path: Path) -> None:
    importer = JsonImporter()
    mapping = JsonFieldMapping("source", "target", "key", True)
    source = tmp_path / "dialog.json"

    project = make_service(importer).import_file(source, "en", "ru", mapping)

    assert importer.calls == [(source, mapping)]
    assert project.documents[0].source_format == "json"
    assert project.documents[0].import_settings == {
        "source_field": "source",
        "target_field": "target",
        "key_field": "key",
        "import_existing_translations": True,
    }


def test_inspects_json_fields_through_configured_adapter(tmp_path: Path) -> None:
    importer = JsonImporter()
    source = tmp_path / "dialog.json"

    fields = make_service(importer).inspect_json_fields(source)

    assert fields == ("key", "source", "target")
    assert importer.calls == [(source, "inspect")]


def test_optional_format_inspectors_require_configured_adapters(tmp_path: Path) -> None:
    service = make_service(JsonImporter())

    with pytest.raises(RuntimeError, match="CSV import support"):
        service.inspect_csv_fields(tmp_path / "dialog.csv")
    with pytest.raises(RuntimeError, match="XML import support"):
        service.inspect_xml_attribute_names(tmp_path / "dialog.xml")


def test_adds_document_at_requested_relative_path(tmp_path: Path) -> None:
    importer = JsonImporter()
    service = make_service(importer)
    repository = Repository()
    session = ProjectSession(tmp_path, tmp_path / "project.db", {})
    project = Project("p", "Demo", "en", "ru")
    source = tmp_path / "dialog.json"

    added = service.add_files(  # type: ignore[arg-type]
        repository,
        session,
        project,
        (source,),
        document_paths={source: "locales/ru/dialog.json"},
    )

    assert added[0].source_path == "locales/ru/dialog.json"
    assert project.documents == list(added)
    assert project.dirty is True
    assert session.metadata["source_files"] == ["locales/ru/dialog.json"]
    assert repository.saved == [project]


@pytest.mark.parametrize(
    "document_path",
    ["../outside.json", "C:/outside.json", "C:outside.json", "//server/share.json", ""],
)
def test_rejects_unsafe_document_path_before_import(
    tmp_path: Path, document_path: str
) -> None:
    importer = JsonImporter()
    service = make_service(importer)
    source = tmp_path / "dialog.json"

    with pytest.raises(ValueError, match="Unsafe project document path"):
        service.add_files(  # type: ignore[arg-type]
            Repository(),
            ProjectSession(tmp_path, tmp_path / "project.db", {}),
            Project("p", "Demo", "en", "ru"),
            (source,),
            document_paths={source: document_path},
        )

    assert importer.calls == []


def test_rejects_unsupported_format() -> None:
    with pytest.raises(ValueError, match="Unsupported localization file format"):
        make_service(JsonImporter()).import_file(Path("strings.yaml"), "en", "ru", None)

from pathlib import Path

import pytest

from locaforge.application.services.project_export import ProjectExportService
from locaforge.domain.document import ProjectDocument
from locaforge.domain.project import Project


class Exporter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def export_file(self, project: Project, destination: Path) -> None:
        self.calls.append((project.name, destination))
        destination.write_text(project.name, encoding="utf-8")


def make_project(source_format: str = "json") -> Project:
    return Project(
        "p",
        "Demo",
        "en",
        "ru",
        documents=[
            ProjectDocument(
                "document-1",
                "dialog.json",
                "nested/dialog.json",
                source_format,
                {},
            )
        ],
    )


def test_exports_documents_through_matching_format_adapter(tmp_path: Path) -> None:
    json_exporter = Exporter()
    service = ProjectExportService(  # type: ignore[arg-type]
        json_exporter, object()
    )

    exported = service.export_all_documents(make_project(), tmp_path / "exported")

    assert exported == (tmp_path / "exported" / "nested" / "dialog.json",)
    assert exported[0].read_text(encoding="utf-8") == "dialog.json"
    assert len(json_exporter.calls) == 1


@pytest.mark.parametrize("source_format", ["po", "csv", "xml", "yaml"])
def test_rejects_unavailable_or_unknown_document_format(
    tmp_path: Path, source_format: str
) -> None:
    service = ProjectExportService(Exporter(), object())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Unsupported project document format"):
        service.export_all_documents(
            make_project(source_format), tmp_path / "exported"
        )


@pytest.mark.parametrize("source_format", ["po", "csv", "xml"])
def test_whole_project_export_requires_configured_adapter(
    tmp_path: Path, source_format: str
) -> None:
    service = ProjectExportService(Exporter(), object())  # type: ignore[arg-type]
    export = getattr(service, f"export_{source_format}")

    with pytest.raises(RuntimeError, match="not configured"):
        export(object(), tmp_path / f"export.{source_format}")

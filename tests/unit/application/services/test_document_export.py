from pathlib import Path

import pytest

from locaforge.application.services.document_export import DocumentExportService
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project


def make_project(*, second_path: str = "nested/second.po") -> Project:
    documents = [
        ProjectDocument(
            id="document-1",
            name="first.json",
            source_path="first.json",
            source_format="json",
            source_document={},
        ),
        ProjectDocument(
            id="document-2",
            name="second.po",
            source_path=second_path,
            source_format="po",
            source_document={},
        ),
    ]
    entries = [
        TranslationEntry(
            id="entry-1",
            key_path=("first",),
            source="First",
            document_id="document-1",
        ),
        TranslationEntry(
            id="entry-2",
            key_path=("second",),
            source="Second",
            document_id="document-2",
        ),
    ]
    return Project("project-1", "Demo", "en", "ru", entries=entries, documents=documents)


def test_exports_selected_documents_in_project_order_and_original_paths(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str, tuple[str, ...]]] = []

    def export(project: Project, source_format: str, destination: Path) -> None:
        calls.append(
            (project.name, source_format, tuple(entry.id for entry in project.entries))
        )
        destination.write_text(project.name, encoding="utf-8")

    destination = tmp_path / "exported"
    exported = DocumentExportService().export(
        make_project(),
        ("document-2", "document-1"),
        destination,
        export,
    )

    assert exported == (
        destination / "first.json",
        destination / "nested" / "second.po",
    )
    assert calls == [
        ("first.json", "json", ("entry-1",)),
        ("second.po", "po", ("entry-2",)),
    ]
    assert (destination / "first.json").read_text(encoding="utf-8") == "first.json"
    assert (destination / "nested" / "second.po").read_text(encoding="utf-8") == "second.po"


@pytest.mark.parametrize("document_ids", [(), ("missing",)])
def test_rejects_empty_or_unknown_selection(
    tmp_path: Path, document_ids: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError):
        DocumentExportService().export(
            make_project(), document_ids, tmp_path / "exported", lambda *_args: None
        )


@pytest.mark.parametrize("unsafe_path", ["../outside.po", "C:/absolute.po"])
def test_rejects_unsafe_document_paths(tmp_path: Path, unsafe_path: str) -> None:
    destination = tmp_path / "exported"

    with pytest.raises(ValueError, match="unsafe export path"):
        DocumentExportService().export(
            make_project(second_path=unsafe_path),
            ("document-2",),
            destination,
            lambda *_args: None,
        )

    assert not destination.exists()


def test_failed_staging_does_not_publish_any_files(tmp_path: Path) -> None:
    destination = tmp_path / "exported"

    def export(project: Project, _source_format: str, staged_path: Path) -> None:
        staged_path.write_text(project.name, encoding="utf-8")
        if project.name == "second.po":
            raise RuntimeError("format export failed")

    with pytest.raises(RuntimeError, match="format export failed"):
        DocumentExportService().export(
            make_project(),
            ("document-1", "document-2"),
            destination,
            export,
        )

    assert not destination.exists()

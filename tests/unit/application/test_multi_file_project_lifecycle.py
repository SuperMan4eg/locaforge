from pathlib import Path

import pytest

from locaforge.app.bootstrap import build_workspace


def test_create_open_and_save_project_with_multiple_json_files(tmp_path: Path) -> None:
    workspace = build_workspace(tmp_path / "data")
    menus = tmp_path / "menus.json"
    dialogs = tmp_path / "dialogs.json"
    menus.write_text('{"play": "Play", "exit": "Exit"}', encoding="utf-8")
    dialogs.write_text('{"hello": "Hello"}', encoding="utf-8")
    destination = tmp_path / "game.lfproj"

    created = workspace.create_from_files(
        (menus, dialogs), destination, "en", "ru"
    )

    assert created.name == "game"
    assert [document.name for document in created.documents] == [
        "menus.json",
        "dialogs.json",
    ]
    assert {document.source_format for document in created.documents} == {"json"}
    assert len(created.entries) == 3
    assert all(entry.document_id is not None for entry in created.entries)

    reopened = build_workspace(tmp_path / "reopened-data")
    project = reopened.open(destination)

    assert len(project.documents) == 2
    assert len(project.entries) == 3
    assert reopened.session.metadata["source_files"] == ["menus.json", "dialogs.json"]
    assert reopened.source_format == "multiple"


def test_multi_file_import_rejects_duplicate_file_names(tmp_path: Path) -> None:
    workspace = build_workspace(tmp_path / "data")
    first = tmp_path / "one" / "strings.json"
    second = tmp_path / "two" / "strings.json"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text('{"one": "One"}', encoding="utf-8")
    second.write_text('{"two": "Two"}', encoding="utf-8")

    with pytest.raises(ValueError, match="unique names"):
        workspace.create_from_files(
            (first, second), tmp_path / "game.lfproj", "en", "ru"
        )

    assert not (tmp_path / "game.lfproj").exists()


def test_export_all_documents_restores_original_names_and_formats(tmp_path: Path) -> None:
    workspace = build_workspace(tmp_path / "data")
    json_source = tmp_path / "menus.json"
    po_source = tmp_path / "dialogs.po"
    json_source.write_text('{"play": "Play"}', encoding="utf-8")
    po_source.write_text('msgid "Hello"\nmsgstr ""\n', encoding="utf-8")
    project = workspace.create_from_files(
        (json_source, po_source), tmp_path / "game.lfproj", "en", "ru"
    )
    for entry in project.entries:
        workspace.edit_translation(
            entry.id, "Играть" if entry.source == "Play" else "Привет"
        )

    exported = workspace.export_all_documents(tmp_path / "exported")

    assert exported == (
        tmp_path / "exported" / "menus.json",
        tmp_path / "exported" / "dialogs.po",
    )
    assert "Играть" in exported[0].read_text(encoding="utf-8")
    assert 'msgstr "Привет"' in exported[1].read_text(encoding="utf-8")


def test_export_all_documents_does_not_publish_staged_files_on_error(
    tmp_path: Path,
) -> None:
    workspace = build_workspace(tmp_path / "data")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"one": "One"}', encoding="utf-8")
    second.write_text('{"two": "Two"}', encoding="utf-8")
    project = workspace.create_from_files(
        (first, second), tmp_path / "game.lfproj", "en", "ru"
    )
    project.documents[1].source_format = "unsupported"

    with pytest.raises(ValueError, match="Unsupported project document format"):
        workspace.export_all_documents(tmp_path / "exported")

    assert not (tmp_path / "exported").exists()

from pathlib import Path

import pytest

from locaforge.app.bootstrap import build_workspace
from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.domain.project_profile import ProjectProfile


def test_create_empty_project_then_import_multiple_files(tmp_path: Path) -> None:
    workspace = build_workspace(tmp_path / "data")
    destination = tmp_path / "game.lfproj"
    profile = ProjectProfile(
        description="A science-fiction strategy game",
        project_type="Game",
        tone="Concise military UI",
    )

    project = workspace.create_project(destination, "Star Fleet", "en", "ru", profile)

    assert project.name == "Star Fleet"
    assert project.documents == []
    assert project.entries == []
    first = tmp_path / "menus.json"
    second = tmp_path / "dialogs.po"
    first.write_text('{"play": "Play"}', encoding="utf-8")
    second.write_text('msgid "Hello"\nmsgstr ""\n', encoding="utf-8")

    added = workspace.import_files((first, second))
    workspace.save()

    assert [document.name for document in added] == ["menus.json", "dialogs.po"]
    assert len(project.entries) == 2
    reopened = build_workspace(tmp_path / "reopened-data")
    restored = reopened.open(destination)
    assert restored.profile == profile
    assert [document.name for document in restored.documents] == [
        "menus.json",
        "dialogs.po",
    ]


def test_import_files_rejects_name_already_used_by_project(tmp_path: Path) -> None:
    workspace = build_workspace(tmp_path / "data")
    workspace.create_project(tmp_path / "game.lfproj", "Game", "en", "ru")
    source = tmp_path / "strings.json"
    source.write_text('{"hello": "Hello"}', encoding="utf-8")
    workspace.import_files((source,))

    with pytest.raises(ValueError, match="unique names"):
        workspace.import_files((source,))


def test_project_settings_can_be_updated_and_reopened(tmp_path: Path) -> None:
    destination = tmp_path / "game.lfproj"
    workspace = build_workspace(tmp_path / "data")
    workspace.create_project(destination, "Old name", "en", "ru")
    profile = ProjectProfile(description="Updated context", tone="Formal")

    workspace.update_project_profile("New name", "en-US", "uk", profile)
    workspace.save()

    reopened = build_workspace(tmp_path / "reopened")
    project = reopened.open(destination)
    assert project.name == "New name"
    assert (project.source_language, project.target_language) == ("en-US", "uk")
    assert project.profile == profile


def test_damaged_project_can_open_backup_as_unsaved_recovery_copy(tmp_path: Path) -> None:
    destination = tmp_path / "game.lfproj"
    workspace = build_workspace(tmp_path / "data")
    workspace.create_project(destination, "Game", "en", "ru")
    workspace.update_project_profile(
        "Game", "en", "ru", ProjectProfile(description="First saved version")
    )
    workspace.save()
    workspace.update_project_profile(
        "Game", "en", "ru", ProjectProfile(description="Second saved version")
    )
    workspace.save()
    destination.write_bytes(b"damaged project")

    recovered_workspace = build_workspace(tmp_path / "recovery-data")
    recovered = recovered_workspace.open_backup(destination)

    assert recovered.profile.description == "First saved version"
    assert recovered.dirty is True
    assert recovered_workspace.session.container_path is None
    assert recovered_workspace.session.metadata["recovered_from"] == str(destination)

    recovered_path = tmp_path / "recovered.lfproj"
    recovered_workspace.save(recovered_path)
    assert recovered_path.is_file()


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
    assert [document.source_location for document in created.documents] == [
        str(menus.resolve()),
        str(dialogs.resolve()),
    ]
    assert len(created.entries) == 3
    assert all(entry.document_id is not None for entry in created.entries)

    reopened = build_workspace(tmp_path / "reopened-data")
    project = reopened.open(destination)

    assert len(project.documents) == 2
    assert len(project.entries) == 3
    assert project.documents[0].source_location == str(menus.resolve())
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


def test_mixed_format_project_survives_save_reopen_and_round_trip_export(
    tmp_path: Path,
) -> None:
    sources = {
        "menus.json": '{"play": "Play"}',
        "items.csv": "key,source,target,category\nsword,Sword,,weapon\n",
        "dialogs.po": '#. Greeting\nmsgctxt "welcome"\nmsgid "Hello"\nmsgstr ""\n',
        "credits.xml": '<credits><line role="lead">Director</line></credits>',
    }
    source_paths: list[Path] = []
    for name, content in sources.items():
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        source_paths.append(path)
    csv_path = tmp_path / "items.csv"
    destination = tmp_path / "mixed.lfproj"
    workspace = build_workspace(tmp_path / "data")
    project = workspace.create_from_files(
        source_paths,
        destination,
        "en",
        "ru",
        {csv_path: CsvFieldMapping("source", "target", "key")},
    )
    translations = {
        "Play": "Играть",
        "Sword": "Меч",
        "Hello": "Привет",
        "Director": "Режиссёр",
    }
    for entry in project.entries:
        workspace.edit_translation(entry.id, translations[entry.source])
    workspace.save()

    reopened = build_workspace(tmp_path / "reopened")
    restored = reopened.open(destination)
    exported = reopened.export_all_documents(tmp_path / "exported")

    assert {document.source_format for document in restored.documents} == {
        "json",
        "csv",
        "po",
        "xml",
    }
    assert {entry.translation for entry in restored.entries} == set(translations.values())
    assert [path.name for path in exported] == list(sources)
    assert '"play": "Играть"' in exported[0].read_text(encoding="utf-8")
    assert "sword,Sword,Меч,weapon" in exported[1].read_text(encoding="utf-8-sig")
    assert '#. Greeting' in exported[2].read_text(encoding="utf-8")
    assert 'msgstr "Привет"' in exported[2].read_text(encoding="utf-8")
    assert '<line role="lead">Режиссёр</line>' in exported[3].read_text(encoding="utf-8")


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


def test_export_selected_documents_only_writes_selected_files(tmp_path: Path) -> None:
    workspace = build_workspace(tmp_path / "data")
    first = tmp_path / "menus.json"
    second = tmp_path / "dialogs.json"
    first.write_text('{"play": "Play"}', encoding="utf-8")
    second.write_text('{"hello": "Hello"}', encoding="utf-8")
    project = workspace.create_from_files(
        (first, second), tmp_path / "game.lfproj", "en", "ru"
    )

    exported = workspace.export_documents(
        (project.documents[1].id,), tmp_path / "selected"
    )

    assert exported == (tmp_path / "selected" / "dialogs.json",)
    assert not (tmp_path / "selected" / "menus.json").exists()


def test_folder_import_preserves_paths_and_allows_duplicate_basenames(
    tmp_path: Path,
) -> None:
    workspace = build_workspace(tmp_path / "data")
    workspace.create_project(tmp_path / "game.lfproj", "Game", "en", "ru")
    first = tmp_path / "source" / "ui" / "strings.json"
    second = tmp_path / "source" / "dialogs" / "strings.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text('{"play": "Play"}', encoding="utf-8")
    second.write_text('{"hello": "Hello"}', encoding="utf-8")

    workspace.import_files(
        (first, second),
        document_paths={
            first: "ui/strings.json",
            second: "dialogs/strings.json",
        },
    )

    assert [document.source_path for document in workspace.project.documents] == [
        "ui/strings.json",
        "dialogs/strings.json",
    ]
    exported = workspace.export_all_documents(tmp_path / "exported-tree")
    assert exported == (
        tmp_path / "exported-tree" / "ui" / "strings.json",
        tmp_path / "exported-tree" / "dialogs" / "strings.json",
    )


def test_remove_document_cleans_project_data_without_deleting_source(
    tmp_path: Path,
) -> None:
    workspace = build_workspace(tmp_path / "data")
    first = tmp_path / "menus.json"
    second = tmp_path / "dialogs.json"
    first.write_text('{"play": "Play"}', encoding="utf-8")
    second.write_text('{"hello": "Hello"}', encoding="utf-8")
    destination = tmp_path / "game.lfproj"
    project = workspace.create_from_files(
        (first, second), destination, "en", "ru"
    )
    removed_document = project.documents[0]
    removed_entry = next(
        entry for entry in project.entries if entry.document_id == removed_document.id
    )
    workspace.edit_translation(removed_entry.id, "Играть")
    workspace.edit_translation(removed_entry.id, "Начать")

    removed = workspace.remove_documents((removed_document.id,))
    workspace.save()

    assert removed == (1, 1)
    assert first.is_file()
    assert [document.name for document in workspace.project.documents] == [
        "dialogs.json"
    ]
    assert all(entry.id != removed_entry.id for entry in workspace.project.entries)
    reopened = build_workspace(tmp_path / "reopened")
    assert [document.name for document in reopened.open(destination).documents] == [
        "dialogs.json"
    ]


def test_refresh_source_preserves_translation_and_reports_changes(tmp_path: Path) -> None:
    workspace = build_workspace(tmp_path / "data")
    source = tmp_path / "strings.json"
    source.write_text('{"a": "One", "b": "Two"}', encoding="utf-8")
    destination = tmp_path / "game.lfproj"
    project = workspace.create_from_files((source,), destination, "en", "ru")
    entries = {entry.key_path: entry for entry in project.entries}
    workspace.edit_translation(entries[("a",)].id, "Один")
    workspace.edit_translation(entries[("b",)].id, "Два")
    document_id = project.documents[0].id
    source.write_text('{"a": "One changed", "c": "Three"}', encoding="utf-8")

    preview = workspace.preview_document_refresh((document_id,))
    applied = workspace.refresh_documents((document_id,))

    assert preview == applied
    assert preview.new_entries == 1
    assert preview.changed_entries == 1
    assert preview.removed_entries == 1
    assert preview.unchanged_entries == 0
    refreshed = {entry.key_path: entry for entry in workspace.project.entries}
    assert set(refreshed) == {("a",), ("c",)}
    assert refreshed[("a",)].source == "One changed"
    assert refreshed[("a",)].translation == "Один"
    assert refreshed[("a",)].status.value == "needs_review"
    assert refreshed[("c",)].translation is None
    workspace.save()

    reopened = build_workspace(tmp_path / "reopened")
    restored = reopened.open(destination)
    assert restored.documents[0].source_location == str(source.resolve())
    assert restored.documents[0].import_settings == {}

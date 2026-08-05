import json
from pathlib import Path

import pytest

from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.domain.entry import EntryStatus
from locaforge.infrastructure.formats.json_format import (
    InvalidJsonError,
    JsonFileExporter,
    JsonFileImporter,
    UnsupportedJsonShapeError,
)


def write_json(path: Path, content: object) -> None:
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")


def test_import_collects_nested_string_values_and_preserves_paths(tmp_path: Path) -> None:
    source = tmp_path / "dialog.json"
    write_json(
        source,
        {"dialog": [{"speaker": "Guide", "text": "Hello"}], "version": 1},
    )

    project = JsonFileImporter().import_file(source, "en", "ru")

    assert project.name == "dialog"
    assert [(entry.key_path, entry.source) for entry in project.entries] == [
        (("dialog", 0, "speaker"), "Guide"),
        (("dialog", 0, "text"), "Hello"),
    ]
    assert project.dirty is False


def test_export_replaces_translations_without_changing_structure(tmp_path: Path) -> None:
    source = tmp_path / "dialog.json"
    destination = tmp_path / "dialog_ru.json"
    original = {
        "dialog": ["Hello", {"text": "Goodbye", "count": 2}],
        "enabled": True,
        "empty": None,
    }
    write_json(source, original)
    project = JsonFileImporter().import_file(source, "en", "ru")
    project.entries[0].set_translation("Привет")
    project.entries[1].set_translation("До свидания")

    JsonFileExporter().export_file(project, destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "dialog": ["Привет", {"text": "До свидания", "count": 2}],
        "enabled": True,
        "empty": None,
    }
    assert json.loads(source.read_text(encoding="utf-8")) == original


def test_export_keeps_source_when_translation_is_missing_or_empty(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    destination = tmp_path / "translated.json"
    write_json(source, {"first": "Hello", "second": "Goodbye"})
    project = JsonFileImporter().import_file(source, "en", "ru")
    project.entries[0].set_translation("")

    JsonFileExporter().export_file(project, destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "first": "Hello",
        "second": "Goodbye",
    }


def test_import_rejects_invalid_json(tmp_path: Path) -> None:
    source = tmp_path / "broken.json"
    source.write_text('{"text": }', encoding="utf-8")

    with pytest.raises(InvalidJsonError):
        JsonFileImporter().import_file(source, "en", "ru")


def test_import_rejects_scalar_root(tmp_path: Path) -> None:
    source = tmp_path / "scalar.json"
    source.write_text('"Hello"', encoding="utf-8")

    with pytest.raises(UnsupportedJsonShapeError, match="root"):
        JsonFileImporter().import_file(source, "en", "ru")


def test_import_maps_selected_language_fields_and_existing_translations(tmp_path: Path) -> None:
    source = tmp_path / "terms.json"
    write_json(
        source,
        [
            {"id": "1", "key": "common_yes", "ch": "是", "tc": "是", "en": "Yes"},
            {"id": "2", "key": "common_no", "ch": "否", "tc": "否", "en": ""},
        ],
    )

    importer = JsonFileImporter()
    project = importer.import_file(
        source,
        "zh",
        "en",
        JsonFieldMapping("ch", "en", "key"),
    )

    assert importer.inspect_fields(source) == ("ch", "en", "id", "key", "tc")
    entries = [
        (entry.key, entry.source, entry.translation, entry.status)
        for entry in project.entries
    ]
    assert entries == [
        ("common_yes", "是", "Yes", EntryStatus.NEEDS_REVIEW),
        ("common_no", "否", None, EntryStatus.UNTRANSLATED),
    ]
    assert project.entries[0].key_path == (0, "en")


def test_import_can_ignore_existing_target_field_values(tmp_path: Path) -> None:
    source = tmp_path / "terms.json"
    write_json(source, [{"key": "common_yes", "ch": "是", "en": "Yes"}])

    project = JsonFileImporter().import_file(
        source,
        "zh",
        "en",
        JsonFieldMapping("ch", "en", "key", import_existing_translations=False),
    )

    assert project.entries[0].translation is None
    assert project.entries[0].status is EntryStatus.UNTRANSLATED

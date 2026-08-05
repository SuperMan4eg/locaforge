from pathlib import Path

import pytest

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.domain.entry import EntryStatus
from locaforge.infrastructure.formats.csv_format import CsvFileFormat, InvalidCsvError


def test_imports_only_mapped_columns_and_preserves_others(tmp_path: Path) -> None:
    source = tmp_path / "strings.csv"
    source.write_text(
        "id;key;ch;en;note\r\n"
        '1;common_yes;是;Yes;"Shown in menu"\r\n'
        "2;common_no;否;;Internal\r\n",
        encoding="utf-8-sig",
    )
    adapter = CsvFileFormat()

    project = adapter.import_file(
        source, "zh", "en", CsvFieldMapping("ch", "en", "key")
    )

    assert adapter.inspect_fields(source) == ("id", "key", "ch", "en", "note")
    assert len(project.entries) == 2
    assert project.entries[0].key == "common_yes"
    assert project.entries[0].translation == "Yes"
    assert project.entries[0].status is EntryStatus.NEEDS_REVIEW
    assert project.entries[1].status is EntryStatus.UNTRANSLATED

    project.entries[1].set_translation("No")
    destination = tmp_path / "translated.csv"
    adapter.export_file(project, destination)
    exported = destination.read_text(encoding="utf-8-sig")

    assert "id;key;ch;en;note\n" in exported.replace("\r\n", "\n")
    assert "2;common_no;否;No;Internal" in exported
    assert "Shown in menu" in exported


def test_imports_tab_separated_file(tmp_path: Path) -> None:
    source = tmp_path / "strings.tsv"
    source.write_text("key\tsource\ttarget\na\tHello\t\n", encoding="utf-8")

    project = CsvFileFormat().import_file(
        source, "en", "ru", CsvFieldMapping("source", "target", "key")
    )

    assert project.entries[0].source == "Hello"
    assert project.source_document["dialect"]["delimiter"] == "\t"


def test_rejects_missing_mapping_field(tmp_path: Path) -> None:
    source = tmp_path / "strings.csv"
    source.write_text("source,target\nHello,\n", encoding="utf-8")

    with pytest.raises(InvalidCsvError, match="do not exist"):
        CsvFileFormat().import_file(
            source, "en", "ru", CsvFieldMapping("missing", "target")
        )

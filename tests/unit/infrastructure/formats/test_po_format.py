from pathlib import Path

import pytest

from locaforge.domain.entry import EntryStatus
from locaforge.infrastructure.formats.po_format import InvalidPoError, PoFileFormat


def test_imports_and_exports_po_semantics(tmp_path: Path) -> None:
    source = tmp_path / "messages.po"
    source.write_text(
        '''msgid ""
msgstr ""
"Language: ru\\n"

#. Button label
#: app/menu.py:10
msgctxt "main-menu"
msgid "Save"
msgstr "Сохранить"
''',
        encoding="utf-8",
    )

    format_adapter = PoFileFormat()
    project = format_adapter.import_file(source, "en", "ru")

    assert len(project.entries) == 1
    entry = project.entries[0]
    assert entry.source == "Save"
    assert entry.translation == "Сохранить"
    assert entry.status is EntryStatus.NEEDS_REVIEW
    assert entry.context == "main-menu"
    assert entry.key == "main-menu"

    entry.set_translation("Сохранить сейчас")
    destination = tmp_path / "exported.po"
    format_adapter.export_file(project, destination)
    exported = destination.read_text(encoding="utf-8")

    assert '#. Button label' in exported
    assert '#: app/menu.py:10' in exported
    assert '"Language: ru\\n"' in exported
    assert 'msgstr "Сохранить сейчас"' in exported


def test_imports_plural_forms_as_separate_entries(tmp_path: Path) -> None:
    source = tmp_path / "plurals.po"
    source.write_text(
        '''msgid "{count} file"
msgid_plural "{count} files"
msgstr[0] "{count} файл"
msgstr[1] "{count} файла"
''',
        encoding="utf-8",
    )

    project = PoFileFormat().import_file(source, "en", "ru")

    assert [entry.source for entry in project.entries] == [
        "{count} file",
        "{count} files",
    ]
    assert [entry.translation for entry in project.entries] == [
        "{count} файл",
        "{count} файла",
    ]
    assert project.entries[0].key_path[-1] == "0"
    assert project.entries[1].key_path[-1] == "1"


def test_rejects_invalid_quoted_value(tmp_path: Path) -> None:
    source = tmp_path / "invalid.po"
    source.write_text('msgid not-quoted\nmsgstr "ok"\n', encoding="utf-8")

    with pytest.raises(InvalidPoError, match="Invalid PO quoted string"):
        PoFileFormat().import_file(source, "en", "ru")

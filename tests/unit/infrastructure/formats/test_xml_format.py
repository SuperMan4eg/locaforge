from pathlib import Path

import pytest

from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.infrastructure.formats.xml_format import InvalidXmlError, XmlFileFormat


def test_imports_leaf_text_and_preserves_xml_structure(tmp_path: Path) -> None:
    source = tmp_path / "dialog.xml"
    source.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<dialog>
  <!-- Keep this comment -->
  <line id="welcome">Hello</line>
  <line id="count">12</line>
  <group><line key="bye">Goodbye</line></group>
</dialog>
''',
        encoding="utf-8",
    )
    adapter = XmlFileFormat()

    project = adapter.import_file(source, "en", "ru")

    assert [entry.source for entry in project.entries] == ["Hello", "Goodbye"]
    assert [entry.key for entry in project.entries] == ["line:welcome", "line:bye"]
    project.entries[0].set_translation("Привет")
    destination = tmp_path / "dialog_ru.xml"
    adapter.export_file(project, destination)
    exported = destination.read_text(encoding="utf-8")

    assert exported.startswith("<?xml")
    assert "<!-- Keep this comment -->" in exported
    assert '<line id="welcome">Привет</line>' in exported
    assert '<line id="count">12</line>' in exported
    assert '<line key="bye">Goodbye</line>' in exported


def test_rejects_invalid_xml(tmp_path: Path) -> None:
    source = tmp_path / "invalid.xml"
    source.write_text("<dialog><line>Hello</dialog>", encoding="utf-8")

    with pytest.raises(InvalidXmlError, match="Cannot import"):
        XmlFileFormat().import_file(source, "en", "ru")


def test_imports_and_exports_selected_text_attributes(tmp_path: Path) -> None:
    source = tmp_path / "ui.xml"
    source.write_text(
        '<ui title="Main menu"><button text="Start game" id="start" /></ui>',
        encoding="utf-8",
    )
    adapter = XmlFileFormat()

    project = adapter.import_file(
        source,
        "en",
        "ru",
        XmlFieldMapping(("text", "title")),
    )

    assert adapter.inspect_attribute_names(source) == ("id", "text", "title")
    assert [entry.source for entry in project.entries] == ["Main menu", "Start game"]
    assert [entry.key for entry in project.entries] == ["ui@title", "button:start@text"]
    project.entries[0].set_translation("Главное меню")
    project.entries[1].set_translation("Начать игру")
    destination = tmp_path / "ui_ru.xml"
    adapter.export_file(project, destination)

    exported = destination.read_text(encoding="utf-8")
    assert 'title="Главное меню"' in exported
    assert 'text="Начать игру"' in exported
    assert 'id="start"' in exported

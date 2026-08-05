from __future__ import annotations

from pathlib import Path

import pytest

from locaforge.domain.glossary import GlossaryTerm
from locaforge.infrastructure.formats.glossary_csv import CsvGlossaryFormat


def test_glossary_csv_round_trips_terms(tmp_path: Path) -> None:
    path = tmp_path / "glossary.csv"
    terms = (
        GlossaryTerm("en", "ru", "Save", "Сохранить"),
        GlossaryTerm("en", "ru", "HP", "ОЗ", case_sensitive=True),
    )

    format_adapter = CsvGlossaryFormat()
    format_adapter.export_file(terms, path)

    assert format_adapter.import_file(path, "en", "ru") == terms


def test_glossary_csv_accepts_utf8_bom_and_default_case_sensitivity(tmp_path: Path) -> None:
    path = tmp_path / "glossary.csv"
    path.write_text("source,target\nSave,Сохранить\n", encoding="utf-8-sig")

    terms = CsvGlossaryFormat().import_file(path, "en", "ru")

    assert terms == (GlossaryTerm("en", "ru", "Save", "Сохранить"),)


def test_glossary_csv_reports_invalid_headers_and_boolean_values(tmp_path: Path) -> None:
    missing_header_path = tmp_path / "missing.csv"
    missing_header_path.write_text("source\nSave\n", encoding="utf-8")
    invalid_boolean_path = tmp_path / "invalid.csv"
    invalid_boolean_path.write_text(
        "source,target,case_sensitive\nSave,Сохранить,perhaps\n", encoding="utf-8"
    )
    format_adapter = CsvGlossaryFormat()

    with pytest.raises(ValueError, match="source and target"):
        format_adapter.import_file(missing_header_path, "en", "ru")
    with pytest.raises(ValueError, match="line 2"):
        format_adapter.import_file(invalid_boolean_path, "en", "ru")

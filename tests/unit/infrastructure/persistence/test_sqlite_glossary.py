from __future__ import annotations

from pathlib import Path

from locaforge.domain.glossary import GlossaryTerm
from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary


def test_glossary_persists_and_updates_term(tmp_path: Path) -> None:
    database_path = tmp_path / "glossary.db"
    glossary = SQLiteGlossary(database_path)
    glossary.store(GlossaryTerm("en", "ru", "Save", "Сохранить"))
    glossary.store(GlossaryTerm("en", "ru", "Save", "Сохранение"))

    reopened = SQLiteGlossary(database_path)
    assert reopened.find_for_sources("en", "ru", ("Save game",)) == (
        GlossaryTerm("en", "ru", "Save", "Сохранение"),
    )


def test_glossary_matches_whole_terms_and_language_pair(tmp_path: Path) -> None:
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    save = GlossaryTerm("en", "ru", "save", "сохранить")
    cat = GlossaryTerm("en", "ru", "cat", "кот")
    glossary.store(save)
    glossary.store(cat)
    glossary.store(GlossaryTerm("en", "de", "save", "speichern"))

    matches = glossary.find_for_sources("en", "ru", ("Save the concatenation",))

    assert matches == (save,)


def test_glossary_honors_case_sensitive_terms(tmp_path: Path) -> None:
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    upper = GlossaryTerm("en", "ru", "HP", "ОЗ", case_sensitive=True)
    glossary.store(upper)

    assert glossary.find_for_sources("en", "ru", ("HP restored",)) == (upper,)
    assert glossary.find_for_sources("en", "ru", ("hp restored",)) == ()


def test_glossary_lists_and_removes_terms_for_language_pair(tmp_path: Path) -> None:
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    exit_term = GlossaryTerm("en", "ru", "Exit", "Выход")
    save_term = GlossaryTerm("en", "ru", "Save", "Сохранить")
    glossary.store(save_term)
    glossary.store(exit_term)
    glossary.store(GlossaryTerm("en", "de", "Exit", "Beenden"))

    assert glossary.list_terms("en", "ru") == (exit_term, save_term)

    glossary.remove(exit_term)

    assert glossary.list_terms("en", "ru") == (save_term,)

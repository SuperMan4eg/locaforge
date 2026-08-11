from __future__ import annotations

from pathlib import Path

from locaforge.domain.glossary import GlossaryTerm
from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary


class CountingSQLiteGlossary(SQLiteGlossary):
    def __init__(self, database_path: Path) -> None:
        self.read_count = 0
        super().__init__(database_path)

    def _read_terms(
        self, source_language: str, target_language: str
    ) -> tuple[GlossaryTerm, ...]:
        self.read_count += 1
        return super()._read_terms(source_language, target_language)


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


def test_glossary_matches_sources_in_one_cached_batch(tmp_path: Path) -> None:
    glossary = CountingSQLiteGlossary(tmp_path / "glossary.db")
    save = GlossaryTerm("en", "ru", "Save", "Сохранить")
    game = GlossaryTerm("en", "ru", "game", "игра")
    glossary.store(save)
    glossary.store(game)

    matches = glossary.find_for_sources_batch(
        "en", "ru", ("Save game", "New game", "Exit")
    )
    repeated = glossary.find_for_sources_batch("en", "ru", ("Save",))

    assert matches == ((game, save), (game,), ())
    assert repeated == ((save,),)
    assert glossary.read_count == 1


def test_glossary_invalidates_only_changed_language_pair(tmp_path: Path) -> None:
    glossary = CountingSQLiteGlossary(tmp_path / "glossary.db")
    save = GlossaryTerm("en", "ru", "Save", "Сохранить")
    exit_term = GlossaryTerm("en", "ru", "Exit", "Выход")
    german_save = GlossaryTerm("en", "de", "Save", "Speichern")
    glossary.store(save)
    glossary.store(german_save)
    assert glossary.find_for_sources_batch("en", "ru", ("Save and Exit",)) == (
        (save,),
    )
    assert glossary.find_for_sources_batch("en", "de", ("Save",)) == (
        (german_save,),
    )

    glossary.store(exit_term)
    assert glossary.find_for_sources_batch("en", "ru", ("Save and Exit",)) == (
        (exit_term, save),
    )
    assert glossary.find_for_sources_batch("en", "de", ("Save",)) == (
        (german_save,),
    )
    glossary.remove(save)
    assert glossary.find_for_sources_batch("en", "ru", ("Save and Exit",)) == (
        (exit_term,),
    )
    assert glossary.read_count == 4

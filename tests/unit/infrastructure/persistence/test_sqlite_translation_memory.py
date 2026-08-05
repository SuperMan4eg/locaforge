from __future__ import annotations

from pathlib import Path

from locaforge.domain.translation_memory import TranslationMemoryRecord
from locaforge.infrastructure.persistence.sqlite_translation_memory import (
    SQLiteTranslationMemory,
)


def test_translation_memory_persists_exact_record(tmp_path: Path) -> None:
    database_path = tmp_path / "shared" / "tm.db"
    memory = SQLiteTranslationMemory(database_path)
    record = TranslationMemoryRecord("en", "ru", "Play", "Играть", "menu")

    memory.store(record)

    reopened = SQLiteTranslationMemory(database_path)
    assert reopened.find_exact("en", "ru", "Play", "menu") == record


def test_translation_memory_updates_existing_exact_record(tmp_path: Path) -> None:
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    memory.store(TranslationMemoryRecord("en", "ru", "Play", "Играть"))

    updated = TranslationMemoryRecord("en", "ru", "Play", "Воспроизвести")
    memory.store(updated)

    assert memory.find_exact("en", "ru", "Play") == updated


def test_translation_memory_separates_language_and_context(tmp_path: Path) -> None:
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    menu = TranslationMemoryRecord("en", "ru", "Open", "Открыть", "menu")
    adjective = TranslationMemoryRecord("en", "ru", "Open", "Открытый", "state")
    memory.store(menu)
    memory.store(adjective)

    assert memory.find_exact("en", "ru", "Open", "menu") == menu
    assert memory.find_exact("en", "ru", "Open", "state") == adjective
    assert memory.find_exact("en", "de", "Open", "menu") is None


def test_translation_memory_lists_filters_and_deletes_records(tmp_path: Path) -> None:
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    menu = TranslationMemoryRecord("en", "ru", "Open", "Открыть", "menu")
    memory.store(menu)
    memory.store(TranslationMemoryRecord("en", "de", "Save", "Speichern"))

    assert memory.list_records("en", "ru", "откр") == (menu,)

    memory.delete(menu)

    assert memory.list_records("en", "ru") == ()


def test_translation_memory_ranks_similar_sources(tmp_path: Path) -> None:
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    memory.store(TranslationMemoryRecord("en", "ru", "Start game", "Начать игру"))
    memory.store(TranslationMemoryRecord("en", "ru", "Start new game", "Начать новую игру"))
    memory.store(TranslationMemoryRecord("en", "ru", "Exit", "Выход"))

    matches = memory.find_similar("en", "ru", "Start a new game", minimum_score=0.5)

    assert [match.record.source for match in matches] == ["Start new game", "Start game"]
    assert matches[0].score > matches[1].score


def test_translation_memory_fuzzy_search_respects_threshold_and_limit(
    tmp_path: Path,
) -> None:
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    memory.store(TranslationMemoryRecord("en", "ru", "Save game", "Сохранить игру"))
    memory.store(TranslationMemoryRecord("en", "ru", "Save file", "Сохранить файл"))

    matches = memory.find_similar(
        "en", "ru", "Save games", limit=1, minimum_score=0.8
    )

    assert len(matches) == 1
    assert matches[0].record.source == "Save game"


def test_translation_memory_limits_fuzzy_comparisons_to_ranked_candidates(
    tmp_path: Path, monkeypatch
) -> None:
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    monkeypatch.setattr(memory, "_MAX_SIMILAR_CANDIDATES", 3)
    for index in range(4):
        memory.store(
            TranslationMemoryRecord("en", "ru", f"Unrelated text {index:03d}", "Текст")
        )
    memory.store(TranslationMemoryRecord("en", "ru", "Save game", "Сохранить игру"))
    comparison_count = 0
    original_matcher = __import__(
        "locaforge.infrastructure.persistence.sqlite_translation_memory",
        fromlist=["SequenceMatcher"],
    ).SequenceMatcher

    class CountingMatcher(original_matcher):
        def ratio(self) -> float:
            nonlocal comparison_count
            comparison_count += 1
            return super().ratio()

    monkeypatch.setattr(
        "locaforge.infrastructure.persistence.sqlite_translation_memory.SequenceMatcher",
        CountingMatcher,
    )

    matches = memory.find_similar("en", "ru", "Save games", minimum_score=0.8)

    assert matches[0].record.source == "Save game"
    assert comparison_count == 3

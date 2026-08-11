from __future__ import annotations

import sqlite3
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
            TranslationMemoryRecord("en", "ru", f"Other {index:03d}", "Текст")
        )
    memory.store(
        TranslationMemoryRecord("en", "ru", "Save game", "Сохранить игру", "menu")
    )
    comparison_count = 0
    original_similarity_ratio = __import__(
        "locaforge.infrastructure.persistence.sqlite_translation_memory",
        fromlist=["_similarity_ratio"],
    )._similarity_ratio

    def counting_similarity_ratio(left: str, right: str, minimum_score: float) -> float:
        nonlocal comparison_count
        comparison_count += 1
        return original_similarity_ratio(left, right, minimum_score)

    monkeypatch.setattr(
        "locaforge.infrastructure.persistence.sqlite_translation_memory._similarity_ratio",
        counting_similarity_ratio,
    )

    matches = memory.find_similar("en", "ru", "Save games", "menu", minimum_score=0.8)

    assert matches[0].record.source == "Save game"
    assert comparison_count == 3


def test_translation_memory_migrates_and_indexes_legacy_source_lengths(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy-tm.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE translation_memory (
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                source TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '',
                translation TEXT NOT NULL,
                PRIMARY KEY (source_language, target_language, source, context)
            )
            """
        )
        connection.execute(
            "INSERT INTO translation_memory VALUES (?, ?, ?, ?, ?)",
            ("en", "ru", "Start game", "", "Начать игру"),
        )

    memory = SQLiteTranslationMemory(database_path)

    assert memory.find_similar("en", "ru", "Start games", minimum_score=0.8)
    with sqlite3.connect(database_path) as connection:
        source_length = connection.execute(
            "SELECT source_length FROM translation_memory"
        ).fetchone()
        indexes = {
            str(row[1])
            for row in connection.execute("PRAGMA index_list(translation_memory)")
        }
        query_plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT source FROM translation_memory "
            "WHERE source_language = ? AND target_language = ? "
            "AND source_length BETWEEN ? AND ?",
            ("en", "ru", 5, 20),
        ).fetchall()
    assert source_length == (len("Start game"),)
    assert "translation_memory_similarity_candidates" in indexes
    assert any(
        "translation_memory_similarity_candidates" in str(row[3])
        for row in query_plan
    )


def test_translation_memory_skips_lengths_that_cannot_reach_threshold(
    tmp_path: Path, monkeypatch
) -> None:
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    memory.store(TranslationMemoryRecord("en", "ru", "Save game", "Сохранить игру"))
    for index in range(20):
        memory.store(
            TranslationMemoryRecord(
                "en",
                "ru",
                f"This candidate is far too long to match the query number {index}",
                "Текст",
            )
        )
    comparison_count = 0
    original_similarity_ratio = __import__(
        "locaforge.infrastructure.persistence.sqlite_translation_memory",
        fromlist=["_similarity_ratio"],
    )._similarity_ratio

    def counting_similarity_ratio(left: str, right: str, minimum_score: float) -> float:
        nonlocal comparison_count
        comparison_count += 1
        return original_similarity_ratio(left, right, minimum_score)

    monkeypatch.setattr(
        "locaforge.infrastructure.persistence.sqlite_translation_memory._similarity_ratio",
        counting_similarity_ratio,
    )

    matches = memory.find_similar("en", "ru", "Save games", minimum_score=0.8)

    assert matches[0].record.source == "Save game"
    assert comparison_count == 1


def test_candidate_length_bounds_are_safe_for_similarity_score() -> None:
    bounds = SQLiteTranslationMemory._candidate_length_bounds(10, 0.8)

    assert bounds == (7, 15)
    assert SQLiteTranslationMemory._candidate_length_bounds(10, 0.0) is None

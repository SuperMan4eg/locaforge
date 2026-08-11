"""Shared SQLite translation memory adapter."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from math import ceil, floor
from pathlib import Path

from rapidfuzz.fuzz import ratio as rapidfuzz_ratio

from locaforge.domain.translation_memory import (
    TranslationMemoryMatch,
    TranslationMemoryRecord,
)


def _similarity_ratio(left: str, right: str, minimum_score: float) -> float:
    score = rapidfuzz_ratio(left, right, score_cutoff=minimum_score * 100.0)
    return float(score) / 100.0


class SQLiteTranslationMemory:
    """Persists exact translation pairs in a shared SQLite database."""

    _MAX_SIMILAR_CANDIDATES = 300

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    def store(self, record: TranslationMemoryRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO translation_memory (
                    source_language, target_language, source, context, translation, source_length
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_language, target_language, source, context)
                DO UPDATE SET
                    translation = excluded.translation,
                    source_length = excluded.source_length
                """,
                (
                    record.source_language,
                    record.target_language,
                    record.source,
                    record.context,
                    record.translation,
                    len(record.source),
                ),
            )

    def list_records(
        self, source_language: str = "", target_language: str = "", search: str = ""
    ) -> tuple[TranslationMemoryRecord, ...]:
        clauses: list[str] = []
        values: list[str] = []
        if source_language:
            clauses.append("source_language = ?")
            values.append(source_language)
        if target_language:
            clauses.append("target_language = ?")
            values.append(target_language)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT source_language, target_language, source, translation, context "
                f"FROM translation_memory {where} "
                "ORDER BY source_language, target_language, source, context",
                values,
            ).fetchall()
        records = tuple(
            TranslationMemoryRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))
            for row in rows
        )
        normalized_search = search.casefold().strip()
        if not normalized_search:
            return records
        return tuple(
            record
            for record in records
            if normalized_search
            in f"{record.source}\n{record.translation}\n{record.context}".casefold()
        )

    def delete(self, record: TranslationMemoryRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM translation_memory WHERE source_language = ? AND target_language = ? "
                "AND source = ? AND context = ?",
                (record.source_language, record.target_language, record.source, record.context),
            )

    def find_exact(
        self,
        source_language: str,
        target_language: str,
        source: str,
        context: str = "",
    ) -> TranslationMemoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT source_language, target_language, source, translation, context
                FROM translation_memory
                WHERE source_language = ?
                  AND target_language = ?
                  AND source = ?
                  AND context = ?
                """,
                (source_language, target_language, source, context),
            ).fetchone()
        if row is None:
            return None
        return TranslationMemoryRecord(
            source_language=str(row[0]),
            target_language=str(row[1]),
            source=str(row[2]),
            translation=str(row[3]),
            context=str(row[4]),
        )

    def find_similar(
        self,
        source_language: str,
        target_language: str,
        source: str,
        context: str = "",
        limit: int = 5,
        minimum_score: float = 0.6,
    ) -> tuple[TranslationMemoryMatch, ...]:
        if limit < 1:
            raise ValueError("Translation memory match limit must be positive")
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError("Minimum translation memory score must be between 0 and 1")
        if not source:
            return ()
        source_length = len(source)
        length_bounds = self._candidate_length_bounds(source_length, minimum_score)
        with self._connect() as connection:
            if length_bounds is None:
                rows = connection.execute(
                    """
                    SELECT source_language, target_language, source, translation, context
                    FROM translation_memory
                    WHERE source_language = ? AND target_language = ?
                    ORDER BY
                        context = ? DESC,
                        ABS(source_length - ?) ASC,
                        source ASC
                    LIMIT ?
                    """,
                    (
                        source_language,
                        target_language,
                        context,
                        source_length,
                        self._MAX_SIMILAR_CANDIDATES,
                    ),
                ).fetchall()
            else:
                minimum_length, maximum_length = length_bounds
                rows = connection.execute(
                    """
                    SELECT source_language, target_language, source, translation, context
                    FROM translation_memory
                    WHERE source_language = ?
                      AND target_language = ?
                      AND source_length BETWEEN ? AND ?
                    ORDER BY
                        context = ? DESC,
                        ABS(source_length - ?) ASC,
                        source ASC
                    LIMIT ?
                    """,
                    (
                        source_language,
                        target_language,
                        minimum_length,
                        maximum_length,
                        context,
                        source_length,
                        self._MAX_SIMILAR_CANDIDATES,
                    ),
                ).fetchall()

        normalized_source = source.casefold()
        matches: list[TranslationMemoryMatch] = []
        for row in rows:
            record = TranslationMemoryRecord(
                source_language=str(row[0]),
                target_language=str(row[1]),
                source=str(row[2]),
                translation=str(row[3]),
                context=str(row[4]),
            )
            score = _similarity_ratio(
                normalized_source,
                record.source.casefold(),
                minimum_score,
            )
            if score >= minimum_score:
                matches.append(TranslationMemoryMatch(record, score))
        matches.sort(
            key=lambda match: (
                match.score,
                match.record.context == context,
            ),
            reverse=True,
        )
        return tuple(matches[:limit])

    @staticmethod
    def _candidate_length_bounds(
        source_length: int, minimum_score: float
    ) -> tuple[int, int] | None:
        """Return lengths that can still reach the requested similarity score."""
        if minimum_score == 0.0:
            return None
        minimum_length = ceil(minimum_score * source_length / (2.0 - minimum_score))
        maximum_length = floor(source_length * (2.0 - minimum_score) / minimum_score)
        return minimum_length, maximum_length

    def _create_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS translation_memory (
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    source TEXT NOT NULL,
                    context TEXT NOT NULL DEFAULT '',
                    translation TEXT NOT NULL,
                    source_length INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (source_language, target_language, source, context)
                )
                """
            )
            columns = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA table_info(translation_memory)"
                ).fetchall()
            }
            if "source_length" not in columns:
                connection.execute(
                    "ALTER TABLE translation_memory ADD COLUMN "
                    "source_length INTEGER NOT NULL DEFAULT 0"
                )
                connection.execute(
                    "UPDATE translation_memory SET source_length = LENGTH(source)"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS translation_memory_similarity_candidates "
                "ON translation_memory(source_language, target_language, source_length)"
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

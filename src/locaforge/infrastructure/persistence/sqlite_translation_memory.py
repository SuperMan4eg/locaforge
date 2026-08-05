"""Shared SQLite translation memory adapter."""

from __future__ import annotations

import sqlite3
from difflib import SequenceMatcher
from pathlib import Path

from locaforge.domain.translation_memory import (
    TranslationMemoryMatch,
    TranslationMemoryRecord,
)


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
                    source_language, target_language, source, context, translation
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_language, target_language, source, context)
                DO UPDATE SET translation = excluded.translation
                """,
                (
                    record.source_language,
                    record.target_language,
                    record.source,
                    record.context,
                    record.translation,
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
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_language, target_language, source, translation, context
                FROM translation_memory
                WHERE source_language = ? AND target_language = ?
                ORDER BY
                    context = ? DESC,
                    ABS(LENGTH(source) - ?) ASC,
                    source ASC
                LIMIT ?
                """,
                (
                    source_language,
                    target_language,
                    context,
                    len(source),
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
            score = SequenceMatcher(
                None, normalized_source, record.source.casefold()
            ).ratio()
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
                    PRIMARY KEY (source_language, target_language, source, context)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

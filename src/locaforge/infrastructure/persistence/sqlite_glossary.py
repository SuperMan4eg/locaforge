"""Shared SQLite glossary adapter."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from locaforge.domain.glossary import GlossaryTerm


class SQLiteGlossary:
    """Persists and matches glossary terms for language pairs."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    def store(self, term: GlossaryTerm) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO glossary (
                    source_language, target_language, source, target, case_sensitive
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_language, target_language, source, case_sensitive)
                DO UPDATE SET target = excluded.target
                """,
                (
                    term.source_language,
                    term.target_language,
                    term.source,
                    term.target,
                    int(term.case_sensitive),
                ),
            )

    def remove(self, term: GlossaryTerm) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM glossary
                WHERE source_language = ?
                  AND target_language = ?
                  AND source = ?
                  AND case_sensitive = ?
                """,
                (
                    term.source_language,
                    term.target_language,
                    term.source,
                    int(term.case_sensitive),
                ),
            )

    def list_terms(
        self,
        source_language: str,
        target_language: str,
    ) -> tuple[GlossaryTerm, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_language, target_language, source, target, case_sensitive
                FROM glossary
                WHERE source_language = ? AND target_language = ?
                ORDER BY source COLLATE NOCASE, case_sensitive
                """,
                (source_language, target_language),
            ).fetchall()
        return tuple(self._term_from_row(row) for row in rows)

    def find_for_sources(
        self,
        source_language: str,
        target_language: str,
        sources: Sequence[str],
    ) -> tuple[GlossaryTerm, ...]:
        if not sources:
            return ()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_language, target_language, source, target, case_sensitive
                FROM glossary
                WHERE source_language = ? AND target_language = ?
                """,
                (source_language, target_language),
            ).fetchall()
        terms = tuple(self._term_from_row(row) for row in rows)
        matched = [
            term
            for term in terms
            if any(self._contains_term(source, term) for source in sources)
        ]
        matched.sort(key=lambda term: (-len(term.source), term.source.casefold()))
        return tuple(matched)

    @staticmethod
    def _contains_term(text: str, term: GlossaryTerm) -> bool:
        flags = 0 if term.case_sensitive else re.IGNORECASE
        pattern = rf"(?<!\w){re.escape(term.source)}(?!\w)"
        return re.search(pattern, text, flags) is not None

    @staticmethod
    def _term_from_row(row: tuple[object, ...]) -> GlossaryTerm:
        return GlossaryTerm(
            source_language=str(row[0]),
            target_language=str(row[1]),
            source=str(row[2]),
            target=str(row[3]),
            case_sensitive=bool(row[4]),
        )

    def _create_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS glossary (
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    case_sensitive INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (
                        source_language, target_language, source, case_sensitive
                    )
                )
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

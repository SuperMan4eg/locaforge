"""Shared SQLite glossary adapter."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from locaforge.domain.glossary import GlossaryTerm


@dataclass(frozen=True, slots=True)
class _CompiledGlossaryTerm:
    term: GlossaryTerm
    source_pattern: re.Pattern[str]


class SQLiteGlossary:
    """Persists and matches glossary terms for language pairs."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._term_cache: dict[
            tuple[str, str], tuple[_CompiledGlossaryTerm, ...]
        ] = {}
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
        self._invalidate_pair(term.source_language, term.target_language)

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
        self._invalidate_pair(term.source_language, term.target_language)

    def list_terms(
        self,
        source_language: str,
        target_language: str,
    ) -> tuple[GlossaryTerm, ...]:
        terms = (
            compiled.term
            for compiled in self._compiled_terms(source_language, target_language)
        )
        return tuple(sorted(terms, key=self._list_sort_key))

    def find_for_sources(
        self,
        source_language: str,
        target_language: str,
        sources: Sequence[str],
    ) -> tuple[GlossaryTerm, ...]:
        matched: list[GlossaryTerm] = []
        seen: set[GlossaryTerm] = set()
        for source_matches in self.find_for_sources_batch(
            source_language, target_language, sources
        ):
            for term in source_matches:
                if term not in seen:
                    seen.add(term)
                    matched.append(term)
        matched.sort(key=self._match_sort_key)
        return tuple(matched)

    def find_for_sources_batch(
        self,
        source_language: str,
        target_language: str,
        sources: Sequence[str],
    ) -> tuple[tuple[GlossaryTerm, ...], ...]:
        """Return relevant terms for each source while loading a language pair once."""
        if not sources:
            return ()
        compiled_terms = self._compiled_terms(source_language, target_language)
        return tuple(
            tuple(
                compiled.term
                for compiled in compiled_terms
                if compiled.source_pattern.search(source) is not None
            )
            for source in sources
        )

    def _compiled_terms(
        self, source_language: str, target_language: str
    ) -> tuple[_CompiledGlossaryTerm, ...]:
        pair = (source_language, target_language)
        cached = self._term_cache.get(pair)
        if cached is not None:
            return cached
        terms = sorted(
            self._read_terms(source_language, target_language),
            key=self._match_sort_key,
        )
        compiled = tuple(
            _CompiledGlossaryTerm(
                term,
                re.compile(
                    rf"(?<!\w){re.escape(term.source)}(?!\w)",
                    0 if term.case_sensitive else re.IGNORECASE,
                ),
            )
            for term in terms
        )
        self._term_cache[pair] = compiled
        return compiled

    def _read_terms(
        self, source_language: str, target_language: str
    ) -> tuple[GlossaryTerm, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_language, target_language, source, target, case_sensitive
                FROM glossary
                WHERE source_language = ? AND target_language = ?
                """,
                (source_language, target_language),
            ).fetchall()
        return tuple(self._term_from_row(row) for row in rows)

    def _invalidate_pair(self, source_language: str, target_language: str) -> None:
        self._term_cache.pop((source_language, target_language), None)

    @staticmethod
    def _match_sort_key(term: GlossaryTerm) -> tuple[int, str]:
        return (-len(term.source), term.source.casefold())

    @staticmethod
    def _list_sort_key(term: GlossaryTerm) -> tuple[str, bool, str, str]:
        return (term.source.casefold(), term.case_sensitive, term.source, term.target)

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

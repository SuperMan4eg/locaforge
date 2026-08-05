"""SQLite implementation of the project repository port."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ValidationCode,
    ValidationIssue,
)
from locaforge.application.errors import EntryNotFoundError, ProjectNotFoundError
from locaforge.domain.entry import EntryStatus, JsonPath, TranslationEntry
from locaforge.domain.history import EntryRevision
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings


class SQLiteProjectRepository:
    """Persists complete projects in a small, self-contained SQLite database."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def create(self, project: Project) -> None:
        with self._connect() as connection:
            if connection.execute("SELECT 1 FROM projects WHERE id = ?", (project.id,)).fetchone():
                raise ValueError(f"A project with id {project.id!r} already exists")
            self._write_project(connection, project)

    def get(self, project_id: str) -> Project:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name, source_language, target_language, source_document, "
                "model_settings, dirty "
                "FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                raise ProjectNotFoundError(f"Project {project_id!r} was not found")
            entry_rows = connection.execute(
                "SELECT id, key_path, source, entry_key, translation, status, locked, "
                "context, max_length, "
                "placeholders "
                "FROM entries WHERE project_id = ? ORDER BY row_order",
                (project_id,),
            ).fetchall()

        return Project(
            id=row["id"],
            name=row["name"],
            source_language=row["source_language"],
            target_language=row["target_language"],
            entries=[self._entry_from_row(entry_row) for entry_row in entry_rows],
            source_document=json.loads(row["source_document"]),
            model_settings=ModelSettings.from_mapping(json.loads(row["model_settings"])),
            dirty=bool(row["dirty"]),
        )

    def save(self, project: Project) -> None:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project.id,)
            ).fetchone()
            if not exists:
                raise ProjectNotFoundError(f"Project {project.id!r} was not found")
            self._write_project(connection, project)

    def mark_project_saved(self, project_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE projects SET dirty = 0 WHERE id = ?", (project_id,)
            )
            if cursor.rowcount == 0:
                raise ProjectNotFoundError(f"Project {project_id!r} was not found")

    def mark_project_dirty(self, project_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE projects SET dirty = 1 WHERE id = ?", (project_id,)
            )
            if cursor.rowcount == 0:
                raise ProjectNotFoundError(f"Project {project_id!r} was not found")

    def get_entry(self, project_id: str, entry_id: str) -> TranslationEntry:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, key_path, source, entry_key, translation, status, locked, "
                "context, max_length, "
                "placeholders "
                "FROM entries WHERE project_id = ? AND id = ?",
                (project_id, entry_id),
            ).fetchone()
        if row is None:
            raise EntryNotFoundError(f"Entry {entry_id!r} was not found in project {project_id!r}")
        return self._entry_from_row(row)

    def update_entry(self, project_id: str, entry: TranslationEntry) -> None:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT translation FROM entries WHERE project_id = ? AND id = ?",
                (project_id, entry.id),
            ).fetchone()
            if existing is None:
                raise EntryNotFoundError(
                    f"Entry {entry.id!r} was not found in project {project_id!r}"
                )
            if existing["translation"] != entry.translation:
                connection.execute(
                    "INSERT INTO entry_history "
                    "(project_id, entry_id, translation, recorded_at) VALUES (?, ?, ?, ?)",
                    (
                        project_id,
                        entry.id,
                        existing["translation"],
                        datetime.now(UTC).isoformat(),
                    ),
                )
            cursor = connection.execute(
                "UPDATE entries SET key_path = ?, source = ?, entry_key = ?, translation = ?, "
                "status = ?, "
                "locked = ?, context = ?, max_length = ?, placeholders = ? "
                "WHERE project_id = ? AND id = ?",
                (*self._entry_values(entry), project_id, entry.id),
            )
            if cursor.rowcount == 0:
                raise EntryNotFoundError(
                    f"Entry {entry.id!r} was not found in project {project_id!r}"
                )
            connection.execute("UPDATE projects SET dirty = 1 WHERE id = ?", (project_id,))

    def update_entries(
        self, project_id: str, entries: Sequence[TranslationEntry]
    ) -> None:
        if not entries:
            return
        with self._connect() as connection:
            existing_translations = self._existing_translations(
                connection, project_id, entries
            )
            if len(existing_translations) != len(entries):
                raise EntryNotFoundError("One or more entries were not found")
            connection.executemany(
                "INSERT INTO entry_history "
                "(project_id, entry_id, translation, recorded_at) VALUES (?, ?, ?, ?)",
                [
                    (
                        project_id,
                        entry.id,
                        existing_translations[entry.id],
                        datetime.now(UTC).isoformat(),
                    )
                    for entry in entries
                    if existing_translations[entry.id] != entry.translation
                ],
            )
            connection.executemany(
                "UPDATE entries SET key_path = ?, source = ?, entry_key = ?, translation = ?, "
                "status = ?, locked = ?, context = ?, max_length = ?, placeholders = ? "
                "WHERE project_id = ? AND id = ?",
                [(*self._entry_values(entry), project_id, entry.id) for entry in entries],
            )
            connection.execute("UPDATE projects SET dirty = 1 WHERE id = ?", (project_id,))

    def update_entry_statuses(
        self, project_id: str, entries: Sequence[TranslationEntry]
    ) -> None:
        if not entries:
            return
        with self._connect() as connection:
            cursor = connection.executemany(
                "UPDATE entries SET status = ? WHERE project_id = ? AND id = ?",
                [(entry.status.value, project_id, entry.id) for entry in entries],
            )
            if cursor.rowcount != len(entries):
                raise EntryNotFoundError("One or more entries were not found")
            connection.execute("UPDATE projects SET dirty = 1 WHERE id = ?", (project_id,))

    def list_entry_revisions(
        self, project_id: str, entry_id: str, limit: int = 50
    ) -> tuple[EntryRevision, ...]:
        if limit < 1:
            raise ValueError("Revision limit must be positive")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, entry_id, translation, recorded_at FROM entry_history "
                "WHERE project_id = ? AND entry_id = ? ORDER BY id DESC LIMIT ?",
                (project_id, entry_id, limit),
            ).fetchall()
        return tuple(self._revision_from_row(row) for row in rows)

    def get_entry_revision(
        self, project_id: str, entry_id: str, revision_id: int
    ) -> EntryRevision:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, entry_id, translation, recorded_at FROM entry_history "
                "WHERE project_id = ? AND entry_id = ? AND id = ?",
                (project_id, entry_id, revision_id),
            ).fetchone()
        if row is None:
            raise EntryNotFoundError(
                f"Revision {revision_id!r} was not found for entry {entry_id!r}"
            )
        return self._revision_from_row(row)

    def replace_validation_issues(
        self, project_id: str, entry_id: str, issues: Sequence[ValidationIssue]
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM validation WHERE project_id = ? AND entry_id = ?",
                (project_id, entry_id),
            )
            connection.executemany(
                "INSERT INTO validation (project_id, entry_id, code, message) "
                "VALUES (?, ?, ?, ?)",
                [
                    (project_id, entry_id, issue.code.value, issue.message)
                    for issue in issues
                ],
            )

    def replace_validation_issues_bulk(
        self,
        project_id: str,
        issues_by_entry: Mapping[str, Sequence[ValidationIssue]],
    ) -> None:
        if not issues_by_entry:
            return
        with self._connect() as connection:
            entry_ids = tuple(issues_by_entry)
            connection.executemany(
                "DELETE FROM validation WHERE project_id = ? AND entry_id = ?",
                [(project_id, entry_id) for entry_id in entry_ids],
            )
            connection.executemany(
                "INSERT INTO validation (project_id, entry_id, code, message) "
                "VALUES (?, ?, ?, ?)",
                [
                    (project_id, entry_id, issue.code.value, issue.message)
                    for entry_id, issues in issues_by_entry.items()
                    for issue in issues
                ],
            )

    def list_validation_issues(self, project_id: str) -> tuple[EntryValidationIssue, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT entry_id, code, message FROM validation "
                "WHERE project_id = ? ORDER BY entry_id, id",
                (project_id,),
            ).fetchall()
        return tuple(
            EntryValidationIssue(
                entry_id=row["entry_id"],
                code=ValidationCode(row["code"]),
                message=row["message"],
            )
            for row in rows
        )

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    source_document TEXT NOT NULL,
                    model_settings TEXT NOT NULL DEFAULT '{}',
                    dirty INTEGER NOT NULL CHECK (dirty IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    row_order INTEGER NOT NULL,
                    key_path TEXT NOT NULL,
                    source TEXT NOT NULL,
                    entry_key TEXT,
                    translation TEXT,
                    status TEXT NOT NULL,
                    locked INTEGER NOT NULL CHECK (locked IN (0, 1)),
                    context TEXT,
                    max_length INTEGER,
                    placeholders TEXT NOT NULL,
                    UNIQUE(project_id, row_order)
                );

                CREATE TABLE IF NOT EXISTS validation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    entry_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    message TEXT NOT NULL,
                    UNIQUE(project_id, entry_id, code, message)
                );

                CREATE TABLE IF NOT EXISTS entry_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    entry_id TEXT NOT NULL,
                    translation TEXT,
                    recorded_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS entry_history_lookup
                ON entry_history(project_id, entry_id, id DESC);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "model_settings" not in columns:
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN model_settings TEXT NOT NULL DEFAULT '{}'"
                )
            entry_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(entries)").fetchall()
            }
            if "entry_key" not in entry_columns:
                connection.execute("ALTER TABLE entries ADD COLUMN entry_key TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _write_project(self, connection: sqlite3.Connection, project: Project) -> None:
        connection.execute(
            """
            INSERT INTO projects (
                id, name, source_language, target_language, source_document,
                model_settings, dirty
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                source_language = excluded.source_language,
                target_language = excluded.target_language,
                source_document = excluded.source_document,
                model_settings = excluded.model_settings,
                dirty = excluded.dirty
            """,
            (
                project.id,
                project.name,
                project.source_language,
                project.target_language,
                json.dumps(project.source_document, ensure_ascii=False),
                json.dumps(project.model_settings.to_dict(), ensure_ascii=False),
                int(project.dirty),
            ),
        )
        connection.execute("DELETE FROM entries WHERE project_id = ?", (project.id,))
        connection.executemany(
            """
            INSERT INTO entries (
                id, project_id, row_order, key_path, source, entry_key, translation, status, locked,
                context, max_length, placeholders
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (entry.id, project.id, index, *self._entry_values(entry))
                for index, entry in enumerate(project.entries)
            ],
        )

    @staticmethod
    def _entry_values(entry: TranslationEntry) -> tuple[object, ...]:
        return (
            json.dumps(entry.key_path, ensure_ascii=False),
            entry.source,
            entry.key,
            entry.translation,
            entry.status.value,
            int(entry.locked),
            entry.context,
            entry.max_length,
            json.dumps(entry.placeholders, ensure_ascii=False),
        )

    @staticmethod
    def _existing_translations(
        connection: sqlite3.Connection,
        project_id: str,
        entries: Sequence[TranslationEntry],
    ) -> dict[str, str | None]:
        existing: dict[str, str | None] = {}
        for offset in range(0, len(entries), 900):
            entry_ids = [entry.id for entry in entries[offset : offset + 900]]
            placeholders = ", ".join("?" for _ in entry_ids)
            rows = connection.execute(
                "SELECT id, translation FROM entries WHERE project_id = ? "
                f"AND id IN ({placeholders})",
                (project_id, *entry_ids),
            ).fetchall()
            existing.update({row["id"]: row["translation"] for row in rows})
        return existing

    @staticmethod
    def _entry_from_row(row: sqlite3.Row) -> TranslationEntry:
        path: JsonPath = tuple(json.loads(row["key_path"]))
        return TranslationEntry(
            id=row["id"],
            key_path=path,
            source=row["source"],
            key=row["entry_key"],
            translation=row["translation"],
            status=EntryStatus(row["status"]),
            locked=bool(row["locked"]),
            context=row["context"],
            max_length=row["max_length"],
            placeholders=tuple(json.loads(row["placeholders"])),
        )

    @staticmethod
    def _revision_from_row(row: sqlite3.Row) -> EntryRevision:
        return EntryRevision(
            revision_id=int(row["id"]),
            entry_id=str(row["entry_id"]),
            translation=row["translation"],
            recorded_at=datetime.fromisoformat(str(row["recorded_at"])),
        )

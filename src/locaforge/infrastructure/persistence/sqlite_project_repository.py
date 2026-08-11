"""SQLite implementation of the project repository port."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ValidationCode,
    ValidationIssue,
)
from locaforge.application.errors import EntryNotFoundError, ProjectNotFoundError
from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import EntryStatus, JsonPath, TranslationEntry
from locaforge.domain.history import EntryRevision, ProjectOperation
from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile
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
                "model_settings, model_settings_override_enabled, project_profile, dirty "
                "FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                raise ProjectNotFoundError(f"Project {project_id!r} was not found")
            entry_rows = connection.execute(
                "SELECT id, key_path, source, entry_key, translation, status, locked, "
                "context, max_length, document_id, model_translation, reviewer_translation, "
                "placeholders "
                "FROM entries WHERE project_id = ? ORDER BY row_order",
                (project_id,),
            ).fetchall()
            document_rows = connection.execute(
                "SELECT id, name, source_path, source_format, source_document, "
                "source_location, import_settings "
                "FROM documents WHERE project_id = ? ORDER BY row_order",
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
            model_settings_override_enabled=bool(row["model_settings_override_enabled"]),
            dirty=bool(row["dirty"]),
            documents=[self._document_from_row(document_row) for document_row in document_rows],
            profile=ProjectProfile.from_mapping(json.loads(row["project_profile"])),
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
        return self.get_entries(project_id, (entry_id,))[0]

    def get_entries(
        self, project_id: str, entry_ids: Sequence[str]
    ) -> tuple[TranslationEntry, ...]:
        if not entry_ids:
            return ()
        selected_ids = tuple(dict.fromkeys(entry_ids))
        with self._connect() as connection:
            entries_by_id = self._entries_by_ids(connection, project_id, selected_ids)
        missing_ids = tuple(entry_id for entry_id in selected_ids if entry_id not in entries_by_id)
        if missing_ids:
            raise EntryNotFoundError(
                f"Entries {missing_ids!r} were not found in project {project_id!r}"
            )
        return tuple(entries_by_id[entry_id] for entry_id in entry_ids)

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
                "locked = ?, context = ?, max_length = ?, placeholders = ?, document_id = ?, "
                "model_translation = ?, reviewer_translation = ? "
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
                "status = ?, locked = ?, context = ?, max_length = ?, placeholders = ?, "
                "document_id = ?, model_translation = ?, reviewer_translation = ? "
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

    def remove_documents(self, project_id: str, document_ids: Sequence[str]) -> None:
        if not document_ids:
            return
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if existing is None:
                raise ProjectNotFoundError(f"Project {project_id!r} was not found")
            document_rows: list[sqlite3.Row] = []
            for offset in range(0, len(document_ids), 900):
                selected = tuple(document_ids[offset : offset + 900])
                placeholders = ", ".join("?" for _ in selected)
                document_rows.extend(
                    connection.execute(
                        "SELECT id FROM documents WHERE project_id = ? "
                        f"AND id IN ({placeholders})",
                        (project_id, *selected),
                    ).fetchall()
                )
            if len(document_rows) != len(set(document_ids)):
                raise ValueError("One or more project documents were not found")
            entry_rows: list[sqlite3.Row] = []
            for offset in range(0, len(document_ids), 900):
                selected = tuple(document_ids[offset : offset + 900])
                placeholders = ", ".join("?" for _ in selected)
                entry_rows.extend(
                    connection.execute(
                        "SELECT id FROM entries WHERE project_id = ? "
                        f"AND document_id IN ({placeholders})",
                        (project_id, *selected),
                    ).fetchall()
                )
            entry_ids = tuple(row["id"] for row in entry_rows)
            for offset in range(0, len(entry_ids), 900):
                selected = entry_ids[offset : offset + 900]
                placeholders = ", ".join("?" for _ in selected)
                connection.execute(
                    "DELETE FROM validation WHERE project_id = ? "
                    f"AND entry_id IN ({placeholders})",
                    (project_id, *selected),
                )
                connection.execute(
                    "DELETE FROM entry_history WHERE project_id = ? "
                    f"AND entry_id IN ({placeholders})",
                    (project_id, *selected),
                )
                connection.execute(
                    "DELETE FROM translation_operation_entries "
                    f"WHERE entry_id IN ({placeholders}) AND operation_id IN "
                    "(SELECT id FROM translation_operations WHERE project_id = ?)",
                    (*selected, project_id),
                )
            connection.execute(
                "DELETE FROM translation_operations WHERE project_id = ? AND NOT EXISTS "
                "(SELECT 1 FROM translation_operation_entries snapshots "
                "WHERE snapshots.operation_id = translation_operations.id)",
                (project_id,),
            )
            for offset in range(0, len(document_ids), 900):
                selected = tuple(document_ids[offset : offset + 900])
                placeholders = ", ".join("?" for _ in selected)
                connection.execute(
                    "DELETE FROM entries WHERE project_id = ? "
                    f"AND document_id IN ({placeholders})",
                    (project_id, *selected),
                )
                connection.execute(
                    "DELETE FROM documents WHERE project_id = ? "
                    f"AND id IN ({placeholders})",
                    (project_id, *selected),
                )
            connection.execute("UPDATE projects SET dirty = 1 WHERE id = ?", (project_id,))

    def remove_entry_artifacts(
        self,
        project_id: str,
        removed_entry_ids: Sequence[str],
        reset_validation_entry_ids: Sequence[str] = (),
    ) -> None:
        with self._connect() as connection:
            for entry_ids in (removed_entry_ids, reset_validation_entry_ids):
                for offset in range(0, len(entry_ids), 900):
                    selected = tuple(entry_ids[offset : offset + 900])
                    placeholders = ", ".join("?" for _ in selected)
                    connection.execute(
                        "DELETE FROM validation WHERE project_id = ? "
                        f"AND entry_id IN ({placeholders})",
                        (project_id, *selected),
                    )
            for offset in range(0, len(removed_entry_ids), 900):
                selected = tuple(removed_entry_ids[offset : offset + 900])
                placeholders = ", ".join("?" for _ in selected)
                connection.execute(
                    "DELETE FROM entry_history WHERE project_id = ? "
                    f"AND entry_id IN ({placeholders})",
                    (project_id, *selected),
                )
                connection.execute(
                    "DELETE FROM translation_operation_entries "
                    f"WHERE entry_id IN ({placeholders}) AND operation_id IN "
                    "(SELECT id FROM translation_operations WHERE project_id = ?)",
                    (*selected, project_id),
                )
            connection.execute(
                "DELETE FROM translation_operations WHERE project_id = ? AND NOT EXISTS "
                "(SELECT 1 FROM translation_operation_entries snapshots "
                "WHERE snapshots.operation_id = translation_operations.id)",
                (project_id,),
            )

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
                    source_location TEXT,
                    import_settings TEXT NOT NULL DEFAULT '{}',
                    model_settings TEXT NOT NULL DEFAULT '{}',
                    model_settings_override_enabled INTEGER NOT NULL DEFAULT 0
                        CHECK (model_settings_override_enabled IN (0, 1)),
                    project_profile TEXT NOT NULL DEFAULT '{}',
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
                    document_id TEXT,
                    model_translation TEXT,
                    reviewer_translation TEXT,
                    UNIQUE(project_id, row_order)
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    row_order INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_format TEXT NOT NULL,
                    source_document TEXT NOT NULL,
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

                CREATE TABLE IF NOT EXISTS translation_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    recorded_at TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT 'Edit translation',
                    undone INTEGER NOT NULL DEFAULT 0 CHECK (undone IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS translation_operation_entries (
                    operation_id INTEGER NOT NULL REFERENCES translation_operations(id)
                        ON DELETE CASCADE,
                    entry_id TEXT NOT NULL,
                    translation TEXT,
                    status TEXT NOT NULL,
                    locked INTEGER NOT NULL DEFAULT 0,
                    model_translation TEXT,
                    reviewer_translation TEXT,
                    resulting_translation TEXT,
                    resulting_status TEXT NOT NULL,
                    resulting_locked INTEGER NOT NULL DEFAULT 0,
                    resulting_model_translation TEXT,
                    resulting_reviewer_translation TEXT,
                    validation_issues TEXT NOT NULL,
                    resulting_validation_issues TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY(operation_id, entry_id)
                );

                CREATE INDEX IF NOT EXISTS translation_operations_latest
                ON translation_operations(project_id, undone, id DESC);
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
            # Existing projects historically always used their stored settings.
            if "model_settings_override_enabled" not in columns:
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN model_settings_override_enabled "
                    "INTEGER NOT NULL DEFAULT 1 CHECK (model_settings_override_enabled IN (0, 1))"
                )
            if "project_profile" not in columns:
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN project_profile TEXT NOT NULL DEFAULT '{}'"
                )
            entry_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(entries)").fetchall()
            }
            if "entry_key" not in entry_columns:
                connection.execute("ALTER TABLE entries ADD COLUMN entry_key TEXT")
            if "document_id" not in entry_columns:
                connection.execute("ALTER TABLE entries ADD COLUMN document_id TEXT")
            if "model_translation" not in entry_columns:
                connection.execute("ALTER TABLE entries ADD COLUMN model_translation TEXT")
            if "reviewer_translation" not in entry_columns:
                connection.execute("ALTER TABLE entries ADD COLUMN reviewer_translation TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS entries_document_lookup "
                "ON entries(project_id, document_id)"
            )
            operation_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(translation_operations)"
                ).fetchall()
            }
            if "label" not in operation_columns:
                connection.execute(
                    "ALTER TABLE translation_operations ADD COLUMN "
                    "label TEXT NOT NULL DEFAULT 'Edit translation'"
                )
            operation_entry_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(translation_operation_entries)"
                ).fetchall()
            }
            if "resulting_validation_issues" not in operation_entry_columns:
                connection.execute(
                    "ALTER TABLE translation_operation_entries ADD COLUMN "
                    "resulting_validation_issues TEXT NOT NULL DEFAULT '[]'"
                )
            if "locked" not in operation_entry_columns:
                connection.execute(
                    "ALTER TABLE translation_operation_entries ADD COLUMN "
                    "locked INTEGER NOT NULL DEFAULT 0"
                )
            if "resulting_locked" not in operation_entry_columns:
                connection.execute(
                    "ALTER TABLE translation_operation_entries ADD COLUMN "
                    "resulting_locked INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS translation_operation_entries_entry_lookup "
                "ON translation_operation_entries(entry_id, operation_id)"
            )
            document_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(documents)").fetchall()
            }
            if "source_location" not in document_columns:
                connection.execute("ALTER TABLE documents ADD COLUMN source_location TEXT")
            if "import_settings" not in document_columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN import_settings TEXT NOT NULL DEFAULT '{}'"
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def record_translation_operation(
        self,
        project_id: str,
        previous_entries: Sequence[TranslationEntry],
        previous_issues: Mapping[str, Sequence[ValidationIssue]],
        label: str,
    ) -> None:
        if not previous_entries:
            return
        entry_ids = tuple(entry.id for entry in previous_entries)
        with self._connect() as connection:
            current_entries = self._entries_by_ids(connection, project_id, entry_ids)
            missing_ids = tuple(
                entry_id for entry_id in entry_ids if entry_id not in current_entries
            )
            if missing_ids:
                raise EntryNotFoundError(
                    f"Entries {missing_ids!r} were not found in project {project_id!r}"
                )
            current_issues = self._validation_issues_by_entry_ids(
                connection, project_id, entry_ids
            )
            connection.execute(
                "DELETE FROM translation_operations WHERE project_id = ? AND undone = 1",
                (project_id,),
            )
            cursor = connection.execute(
                "INSERT INTO translation_operations (project_id, recorded_at, label) "
                "VALUES (?, ?, ?)",
                (project_id, datetime.now(UTC).isoformat(), label),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Cannot allocate translation operation id")
            operation_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO translation_operation_entries "
                "(operation_id, entry_id, translation, status, locked, model_translation, "
                "reviewer_translation, resulting_translation, resulting_status, "
                "resulting_locked, resulting_model_translation, resulting_reviewer_translation, "
                "validation_issues, resulting_validation_issues) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        operation_id,
                        entry.id,
                        entry.translation,
                        entry.status.value,
                        int(entry.locked),
                        entry.model_translation,
                        entry.reviewer_translation,
                        current.translation,
                        current.status.value,
                        int(current.locked),
                        current.model_translation,
                        current.reviewer_translation,
                        json.dumps(
                            [
                                {"code": issue.code.value, "message": issue.message}
                                for issue in previous_issues.get(entry.id, ())
                            ],
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            [
                                {"code": code, "message": message}
                                for code, message in current_issues.get(entry.id, ())
                            ],
                            ensure_ascii=False,
                        ),
                    )
                    for entry in previous_entries
                    for current in (current_entries[entry.id],)
                ],
            )

    def next_undo_operation_label(self, project_id: str) -> str | None:
        return self._next_operation_label(project_id, undone=False)

    def next_redo_operation_label(self, project_id: str) -> str | None:
        return self._next_operation_label(project_id, undone=True)

    def list_translation_operations(
        self, project_id: str, limit: int = 50
    ) -> tuple[ProjectOperation, ...]:
        if limit < 1:
            return ()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT operation.id, operation.label, operation.recorded_at, "
                "operation.undone, COUNT(snapshot.entry_id) AS entry_count "
                "FROM translation_operations operation "
                "JOIN translation_operation_entries snapshot "
                "ON snapshot.operation_id = operation.id "
                "WHERE operation.project_id = ? GROUP BY operation.id "
                "ORDER BY operation.id DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return tuple(
            ProjectOperation(
                operation_id=int(row["id"]),
                label=str(row["label"]),
                recorded_at=datetime.fromisoformat(str(row["recorded_at"])),
                undone=bool(row["undone"]),
                entry_count=int(row["entry_count"]),
            )
            for row in rows
        )

    def _next_operation_label(self, project_id: str, *, undone: bool) -> str | None:
        order = "ASC" if undone else "DESC"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT label FROM translation_operations "
                f"WHERE project_id = ? AND undone = ? ORDER BY id {order} LIMIT 1",
                (project_id, int(undone)),
            ).fetchone()
        return None if row is None else str(row["label"])

    def has_undoable_translation_operation(self, project_id: str) -> bool:
        with self._connect() as connection:
            operation = connection.execute(
                "SELECT id FROM translation_operations "
                "WHERE project_id = ? AND undone = 0 ORDER BY id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if operation is None:
                return False
            mismatch = connection.execute(
                "SELECT 1 FROM translation_operation_entries snapshot "
                "LEFT JOIN entries entry ON entry.project_id = ? "
                "AND entry.id = snapshot.entry_id "
                "WHERE snapshot.operation_id = ? AND (entry.id IS NULL "
                "OR entry.translation IS NOT snapshot.resulting_translation "
                "OR entry.status IS NOT snapshot.resulting_status "
                "OR entry.locked IS NOT snapshot.resulting_locked "
                "OR entry.model_translation IS NOT snapshot.resulting_model_translation "
                "OR entry.reviewer_translation IS NOT "
                "snapshot.resulting_reviewer_translation) LIMIT 1",
                (project_id, operation["id"]),
            ).fetchone()
            return mismatch is None and self._operation_validation_matches(
                connection,
                project_id,
                int(operation["id"]),
                "resulting_validation_issues",
            )

    def undo_last_translation_operation(
        self, project_id: str
    ) -> tuple[TranslationEntry, ...]:
        restored_entry_ids: tuple[str, ...] = ()
        with self._connect() as connection:
            operation = connection.execute(
                "SELECT id FROM translation_operations "
                "WHERE project_id = ? AND undone = 0 ORDER BY id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if operation is None:
                return ()
            operation_id = int(operation["id"])
            if not self._operation_validation_matches(
                connection,
                project_id,
                operation_id,
                "resulting_validation_issues",
            ):
                raise ValueError(
                    "Cannot undo operation because validation results changed later"
                )
            snapshots = connection.execute(
                "SELECT entry_id, translation, status, locked, model_translation, "
                "reviewer_translation, resulting_translation, resulting_status, "
                "resulting_locked, resulting_model_translation, resulting_reviewer_translation, "
                "validation_issues "
                "FROM translation_operation_entries WHERE operation_id = ?",
                (operation_id,),
            ).fetchall()
            restored_entry_ids = tuple(str(snapshot["entry_id"]) for snapshot in snapshots)
            current_states = self._entry_states_by_ids(
                connection, project_id, restored_entry_ids
            )
            for snapshot in snapshots:
                entry_id = str(snapshot["entry_id"])
                current_state = current_states.get(entry_id)
                if current_state is None:
                    raise EntryNotFoundError(
                        f"Entry {entry_id!r} from translation undo was not found"
                    )
                expected_state = (
                    snapshot["resulting_translation"],
                    snapshot["resulting_status"],
                    snapshot["resulting_locked"],
                    snapshot["resulting_model_translation"],
                    snapshot["resulting_reviewer_translation"],
                )
                if current_state != expected_state:
                    raise ValueError(
                        "Cannot undo translation because one or more entries were edited later"
                    )
            recorded_at = datetime.now(UTC).isoformat()
            connection.executemany(
                "INSERT INTO entry_history "
                "(project_id, entry_id, translation, recorded_at) VALUES (?, ?, ?, ?)",
                [
                    (project_id, entry_id, current_states[entry_id][0], recorded_at)
                    for entry_id in restored_entry_ids
                ],
            )
            connection.executemany(
                "UPDATE entries SET translation = ?, status = ?, locked = ?, "
                "model_translation = ?, reviewer_translation = ? "
                "WHERE project_id = ? AND id = ?",
                [
                    (
                        snapshot["translation"],
                        snapshot["status"],
                        snapshot["locked"],
                        snapshot["model_translation"],
                        snapshot["reviewer_translation"],
                        project_id,
                        snapshot["entry_id"],
                    )
                    for snapshot in snapshots
                ],
            )
            connection.executemany(
                "DELETE FROM validation WHERE project_id = ? AND entry_id = ?",
                [(project_id, entry_id) for entry_id in restored_entry_ids],
            )
            connection.executemany(
                "INSERT INTO validation (project_id, entry_id, code, message) "
                "VALUES (?, ?, ?, ?)",
                [
                    (project_id, snapshot["entry_id"], issue["code"], issue["message"])
                    for snapshot in snapshots
                    for issue in json.loads(snapshot["validation_issues"])
                ],
            )
            connection.execute(
                "UPDATE translation_operations SET undone = 1 WHERE id = ?",
                (operation_id,),
            )
            connection.execute("UPDATE projects SET dirty = 1 WHERE id = ?", (project_id,))
        return self.get_entries(project_id, restored_entry_ids)

    def has_redoable_translation_operation(self, project_id: str) -> bool:
        with self._connect() as connection:
            operation = connection.execute(
                "SELECT id FROM translation_operations "
                "WHERE project_id = ? AND undone = 1 ORDER BY id ASC LIMIT 1",
                (project_id,),
            ).fetchone()
            if operation is None:
                return False
            mismatch = connection.execute(
                "SELECT 1 FROM translation_operation_entries snapshot "
                "LEFT JOIN entries entry ON entry.project_id = ? AND entry.id = snapshot.entry_id "
                "WHERE snapshot.operation_id = ? AND (entry.id IS NULL "
                "OR entry.translation IS NOT snapshot.translation "
                "OR entry.status IS NOT snapshot.status "
                "OR entry.locked IS NOT snapshot.locked "
                "OR entry.model_translation IS NOT snapshot.model_translation "
                "OR entry.reviewer_translation IS NOT snapshot.reviewer_translation) LIMIT 1",
                (project_id, operation["id"]),
            ).fetchone()
            return mismatch is None and self._operation_validation_matches(
                connection,
                project_id,
                int(operation["id"]),
                "validation_issues",
            )

    def redo_last_translation_operation(
        self, project_id: str
    ) -> tuple[TranslationEntry, ...]:
        restored_entry_ids: tuple[str, ...] = ()
        with self._connect() as connection:
            operation = connection.execute(
                "SELECT id FROM translation_operations "
                "WHERE project_id = ? AND undone = 1 ORDER BY id ASC LIMIT 1",
                (project_id,),
            ).fetchone()
            if operation is None:
                return ()
            operation_id = int(operation["id"])
            if not self._operation_validation_matches(
                connection,
                project_id,
                operation_id,
                "validation_issues",
            ):
                raise ValueError(
                    "Cannot redo operation because validation results changed later"
                )
            snapshots = connection.execute(
                "SELECT entry_id, translation, status, locked, model_translation, "
                "reviewer_translation, resulting_translation, resulting_status, "
                "resulting_locked, resulting_model_translation, resulting_reviewer_translation, "
                "resulting_validation_issues FROM translation_operation_entries "
                "WHERE operation_id = ?",
                (operation_id,),
            ).fetchall()
            restored_entry_ids = tuple(str(snapshot["entry_id"]) for snapshot in snapshots)
            current_states = self._entry_states_by_ids(
                connection, project_id, restored_entry_ids
            )
            for snapshot in snapshots:
                entry_id = str(snapshot["entry_id"])
                current_state = current_states.get(entry_id)
                expected = (
                    snapshot["translation"],
                    snapshot["status"],
                    snapshot["locked"],
                    snapshot["model_translation"],
                    snapshot["reviewer_translation"],
                )
                if current_state is None:
                    raise EntryNotFoundError(
                        f"Entry {entry_id!r} from translation redo was not found"
                    )
                if current_state != expected:
                    raise ValueError(
                        "Cannot redo translation because one or more entries were edited later"
                    )
            connection.executemany(
                "UPDATE entries SET translation = ?, status = ?, locked = ?, "
                "model_translation = ?, reviewer_translation = ? "
                "WHERE project_id = ? AND id = ?",
                [
                    (
                        snapshot["resulting_translation"],
                        snapshot["resulting_status"],
                        snapshot["resulting_locked"],
                        snapshot["resulting_model_translation"],
                        snapshot["resulting_reviewer_translation"],
                        project_id,
                        snapshot["entry_id"],
                    )
                    for snapshot in snapshots
                ],
            )
            connection.executemany(
                "DELETE FROM validation WHERE project_id = ? AND entry_id = ?",
                [(project_id, entry_id) for entry_id in restored_entry_ids],
            )
            connection.executemany(
                "INSERT INTO validation (project_id, entry_id, code, message) "
                "VALUES (?, ?, ?, ?)",
                [
                    (project_id, snapshot["entry_id"], issue["code"], issue["message"])
                    for snapshot in snapshots
                    for issue in json.loads(snapshot["resulting_validation_issues"])
                ],
            )
            connection.execute(
                "UPDATE translation_operations SET undone = 0 WHERE id = ?", (operation_id,)
            )
            connection.execute("UPDATE projects SET dirty = 1 WHERE id = ?", (project_id,))
        return self.get_entries(project_id, restored_entry_ids)

    def _operation_validation_matches(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        operation_id: int,
        snapshot_column: str,
    ) -> bool:
        if snapshot_column not in {"validation_issues", "resulting_validation_issues"}:
            raise ValueError(f"Unknown validation snapshot column: {snapshot_column}")
        snapshots = connection.execute(
            f"SELECT entry_id, {snapshot_column} AS issues "
            "FROM translation_operation_entries WHERE operation_id = ?",
            (operation_id,),
        ).fetchall()
        current_by_entry = self._validation_issues_by_entry_ids(
            connection,
            project_id,
            tuple(str(snapshot["entry_id"]) for snapshot in snapshots),
        )
        for snapshot in snapshots:
            current_issues = sorted(current_by_entry[str(snapshot["entry_id"])])
            expected_issues = sorted(
                (issue["code"], issue["message"])
                for issue in json.loads(snapshot["issues"])
            )
            if current_issues != expected_issues:
                return False
        return True

    def _write_project(self, connection: sqlite3.Connection, project: Project) -> None:
        connection.execute(
            """
            INSERT INTO projects (
                id, name, source_language, target_language, source_document,
                model_settings, model_settings_override_enabled, project_profile, dirty
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                source_language = excluded.source_language,
                target_language = excluded.target_language,
                source_document = excluded.source_document,
                model_settings = excluded.model_settings,
                model_settings_override_enabled = excluded.model_settings_override_enabled,
                project_profile = excluded.project_profile,
                dirty = excluded.dirty
            """,
            (
                project.id,
                project.name,
                project.source_language,
                project.target_language,
                json.dumps(project.source_document, ensure_ascii=False),
                json.dumps(project.model_settings.to_dict(), ensure_ascii=False),
                int(project.model_settings_override_enabled),
                json.dumps(project.profile.to_dict(), ensure_ascii=False),
                int(project.dirty),
            ),
        )
        connection.execute("DELETE FROM entries WHERE project_id = ?", (project.id,))
        connection.execute("DELETE FROM documents WHERE project_id = ?", (project.id,))
        connection.executemany(
            "INSERT INTO documents "
            "(id, project_id, row_order, name, source_path, source_format, source_document, "
            "source_location, import_settings) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    document.id,
                    project.id,
                    index,
                    document.name,
                    document.source_path,
                    document.source_format,
                    json.dumps(document.source_document, ensure_ascii=False),
                    document.source_location,
                    json.dumps(document.import_settings, ensure_ascii=False),
                )
                for index, document in enumerate(project.documents)
            ],
        )
        connection.executemany(
            """
            INSERT INTO entries (
                id, project_id, row_order, key_path, source, entry_key, translation, status, locked,
                context, max_length, placeholders, document_id, model_translation,
                reviewer_translation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            entry.document_id,
            entry.model_translation,
            entry.reviewer_translation,
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

    @classmethod
    def _entries_by_ids(
        cls,
        connection: sqlite3.Connection,
        project_id: str,
        entry_ids: Sequence[str],
    ) -> dict[str, TranslationEntry]:
        entries: dict[str, TranslationEntry] = {}
        for offset in range(0, len(entry_ids), 900):
            selected = tuple(entry_ids[offset : offset + 900])
            if not selected:
                continue
            placeholders = ", ".join("?" for _ in selected)
            rows = connection.execute(
                "SELECT id, key_path, source, entry_key, translation, status, locked, "
                "context, max_length, document_id, model_translation, reviewer_translation, "
                "placeholders FROM entries WHERE project_id = ? "
                f"AND id IN ({placeholders})",
                (project_id, *selected),
            ).fetchall()
            entries.update(
                (str(row["id"]), cls._entry_from_row(row)) for row in rows
            )
        return entries

    @staticmethod
    def _entry_states_by_ids(
        connection: sqlite3.Connection,
        project_id: str,
        entry_ids: Sequence[str],
    ) -> dict[str, tuple[object, ...]]:
        states: dict[str, tuple[object, ...]] = {}
        for offset in range(0, len(entry_ids), 900):
            selected = tuple(entry_ids[offset : offset + 900])
            if not selected:
                continue
            placeholders = ", ".join("?" for _ in selected)
            rows = connection.execute(
                "SELECT id, translation, status, locked, model_translation, "
                "reviewer_translation FROM entries WHERE project_id = ? "
                f"AND id IN ({placeholders})",
                (project_id, *selected),
            ).fetchall()
            states.update(
                (
                    str(row["id"]),
                    (
                        row["translation"],
                        row["status"],
                        row["locked"],
                        row["model_translation"],
                        row["reviewer_translation"],
                    ),
                )
                for row in rows
            )
        return states

    @staticmethod
    def _validation_issues_by_entry_ids(
        connection: sqlite3.Connection,
        project_id: str,
        entry_ids: Sequence[str],
    ) -> dict[str, list[tuple[str, str]]]:
        issues: dict[str, list[tuple[str, str]]] = {
            entry_id: [] for entry_id in entry_ids
        }
        for offset in range(0, len(entry_ids), 900):
            selected = tuple(entry_ids[offset : offset + 900])
            if not selected:
                continue
            placeholders = ", ".join("?" for _ in selected)
            rows = connection.execute(
                "SELECT entry_id, code, message FROM validation "
                "WHERE project_id = ? "
                f"AND entry_id IN ({placeholders})",
                (project_id, *selected),
            ).fetchall()
            for row in rows:
                issues[str(row["entry_id"])].append(
                    (str(row["code"]), str(row["message"]))
                )
        return issues

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
            document_id=row["document_id"],
            model_translation=row["model_translation"],
            reviewer_translation=row["reviewer_translation"],
        )

    @staticmethod
    def _document_from_row(row: sqlite3.Row) -> ProjectDocument:
        return ProjectDocument(
            id=row["id"],
            name=row["name"],
            source_path=row["source_path"],
            source_format=row["source_format"],
            source_document=json.loads(row["source_document"]),
            source_location=row["source_location"],
            import_settings=json.loads(row["import_settings"]),
        )

    @staticmethod
    def _revision_from_row(row: sqlite3.Row) -> EntryRevision:
        return EntryRevision(
            revision_id=int(row["id"]),
            entry_id=str(row["entry_id"]),
            translation=row["translation"],
            recorded_at=datetime.fromisoformat(str(row["recorded_at"])),
        )
